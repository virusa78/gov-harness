#!/usr/bin/env python3
"""Install and verify a versioned governance harness.

Exit codes:
  0  success / clean
  2  local drift reported by check or diff
  3  integrity, configuration, or safe-refusal failure
"""

from __future__ import annotations

import argparse
import base64
import difflib
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


LOCK_NAME = ".harness.lock"
MANIFEST_NAME = "release/manifest.json"
ADOPT_DIR = ".artifacts/harness-adopt"
TOKEN_ENV = "GOV_HARNESS_TOKEN"
PLACEHOLDER = __import__("re").compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
TARGET_NAME = __import__("re").compile(r"[a-z][a-z0-9-]*")
PROFILE_NAME = __import__("re").compile(r"[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*)?")
TARGET_ROOT_PARAM = "target_root"


class HarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    name: str
    root: str
    params: dict[str, str]


@dataclass(frozen=True)
class ReleaseFile:
    source: str
    destination: str
    layer: str
    profile: str | None
    templated: bool
    executable: bool
    sha256: str
    target: str | None = None
    params: dict[str, str] | None = None


@dataclass(frozen=True)
class Release:
    root: Path
    manifest: dict[str, object]
    files: tuple[ReleaseFile, ...]
    archive_sha256: str
    cleanup: Path | None = None
    targets: tuple[Target, ...] = ()
    managed_roots: tuple[str, ...] = ()
    profile_info: tuple[tuple[str, str], ...] = ()


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"{label} must be a JSON object")
    return value


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalized_relative(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise HarnessError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise HarnessError(f"unsafe {label}: {raw!r}")
    normalized = path.as_posix()
    if normalized != raw or "\\" in raw:
        raise HarnessError(f"{label} is not normalized POSIX: {raw!r}")
    return normalized


def string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise HarnessError(f"{label} must be a list of strings")
    return list(value)


def parse_targets(manifest: dict[str, object]) -> tuple[list[Target], list[str]]:
    declared = string_list(manifest.get("target_params", []), "target_params")
    if len(declared) != len(set(declared)):
        raise HarnessError("target_params contains duplicates")
    for name in declared:
        if not PLACEHOLDER.fullmatch("{{" + name + "}}"):
            raise HarnessError(f"invalid target parameter name: {name!r}")
    if TARGET_ROOT_PARAM in declared:
        raise HarnessError(f"{TARGET_ROOT_PARAM} is reserved and set by the installer")
    global_params = set(string_list(manifest.get("required_params", []), "required_params"))
    if overlap := sorted(global_params & set(declared)):
        raise HarnessError(f"target_params overlap required_params: {', '.join(overlap)}")

    raw = manifest.get("targets", [])
    if not isinstance(raw, list):
        raise HarnessError("manifest targets must be a list")
    targets: list[Target] = []
    names: set[str] = set()
    roots: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise HarnessError(f"targets[{index}] must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not TARGET_NAME.fullmatch(name):
            raise HarnessError(f"invalid target name: {name!r}")
        if name in names:
            raise HarnessError(f"duplicate target: {name}")
        names.add(name)
        target_root = normalized_relative(item.get("root"), f"targets[{index}].root")
        if target_root in roots:
            raise HarnessError(f"duplicate target root: {target_root}")
        roots.add(target_root)
        raw_params = item.get("params", {})
        if not isinstance(raw_params, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_params.items()
        ):
            raise HarnessError(f"target {name} params must be a string-to-string object")
        if set(raw_params) != set(declared):
            raise HarnessError(
                f"target {name} must declare exactly target_params: {', '.join(sorted(declared))}"
            )
        targets.append(Target(name, target_root, dict(raw_params)))
    if not declared and not targets:
        return [], []
    if declared and not targets:
        raise HarnessError("target_params declared without any targets")
    return targets, declared


def parse_managed_roots(manifest: dict[str, object]) -> list[str]:
    raw = string_list(manifest.get("managed_roots", []), "managed_roots")
    roots = [normalized_relative(item, "managed_roots entry") for item in raw]
    if len(roots) != len(set(roots)):
        raise HarnessError("managed_roots contains duplicates")
    for outer in roots:
        for inner in roots:
            if outer != inner and inner.startswith(outer + "/"):
                raise HarnessError(f"managed root {inner} nests inside {outer}")
    return sorted(roots)


def profile_family(name: str | None) -> str | None:
    if name and "/" in name:
        return name.split("/", 1)[0]
    return None


def parse_profile_info(
    manifest: dict[str, object], declared: set[str]
) -> list[tuple[str, str]]:
    raw = manifest.get("profile_info", [])
    if not isinstance(raw, list):
        raise HarnessError("profile_info must be a list")
    seen: set[str] = set()
    info: list[tuple[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise HarnessError(f"profile_info[{index}] must be an object")
        name = item.get("name")
        description = item.get("description")
        if not isinstance(name, str) or not isinstance(description, str):
            raise HarnessError(f"profile_info[{index}] needs string name and description")
        if name in seen:
            raise HarnessError(f"profile_info duplicates profile: {name}")
        if name not in declared:
            raise HarnessError(f"profile_info describes unknown profile: {name}")
        seen.add(name)
        info.append((name, description))
    return info


def within_root(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def protected_by_override(path: str, overrides: Iterable[str]) -> bool:
    """An override protects its own path and the directory it names.

    Overrides are written as `<skills_root>/<name>/SKILL.md`, but a skill also
    owns its sibling assets (`examples/`, `templates/`). Protecting the parent
    directory keeps those from being pruned as strays.
    """
    if matches_override(path, overrides):
        return True
    for pattern in overrides:
        if any(character in pattern for character in "*?"):
            continue
        parent = PurePosixPath(pattern).parent.as_posix()
        if parent not in {"", "."} and within_root(path, parent):
            return True
    return False


def stray_files(
    project: Path,
    managed_roots: Iterable[str],
    keep: Iterable[str],
    overrides: Iterable[str],
) -> list[str]:
    kept = set(keep)
    found: set[str] = set()
    for root in managed_roots:
        base = project / normalized_relative(root, "managed root")
        if not base.is_dir() or base.is_symlink():
            continue
        for path in base.rglob("*"):
            relative = path.relative_to(project).as_posix()
            if path.is_symlink():
                raise HarnessError(f"refusing to prune through symlink: {relative}")
            if not path.is_file():
                continue
            if relative in kept or relative == LOCK_NAME:
                continue
            if protected_by_override(relative, overrides):
                continue
            found.add(relative)
    return sorted(found)


def prune_empty_directories(project: Path, managed_roots: Iterable[str]) -> None:
    for root in managed_roots:
        base = project / normalized_relative(root, "managed root")
        if not base.is_dir() or base.is_symlink():
            continue
        candidates = [path for path in base.rglob("*") if path.is_dir()] + [base]
        for path in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
            if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
                path.rmdir()
        cursor = base.parent
        while cursor != project and project in cursor.parents:
            if not cursor.is_dir() or cursor.is_symlink() or any(cursor.iterdir()):
                break
            cursor.rmdir()
            cursor = cursor.parent


def parse_release(root: Path, expected_version: str, archive_sha256: str) -> Release:
    manifest = read_json(root / MANIFEST_NAME, "release manifest")
    schema = manifest.get("schema_version")
    if schema not in {1, 2}:
        raise HarnessError("unsupported release manifest schema")
    targets, _target_params = parse_targets(manifest)
    if schema == 1 and targets:
        raise HarnessError("manifest targets require schema_version 2")
    managed_roots = parse_managed_roots(manifest)
    if schema == 1 and managed_roots:
        raise HarnessError("manifest managed_roots require schema_version 2")
    if manifest.get("version") != expected_version:
        raise HarnessError(
            f"release version mismatch: expected {expected_version}, got {manifest.get('version')}"
        )
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise HarnessError("release manifest files must be a non-empty list")
    files: list[ReleaseFile] = []
    destinations: dict[str, tuple[str, str | None]] = {}
    for index, raw in enumerate(raw_files):
        if not isinstance(raw, dict):
            raise HarnessError(f"manifest files[{index}] must be an object")
        source = normalized_relative(raw.get("source"), f"files[{index}].source")
        destination = normalized_relative(
            raw.get("destination"), f"files[{index}].destination"
        )
        fanout = raw.get("fanout", False)
        if not isinstance(fanout, bool):
            raise HarnessError(f"fanout flag for {destination} must be boolean")
        marker = "{{" + TARGET_ROOT_PARAM + "}}"
        if fanout:
            if schema != 2:
                raise HarnessError(f"fanout requires schema_version 2: {destination}")
            if not targets:
                raise HarnessError(f"fanout file has no targets: {destination}")
            if not destination.startswith(marker + "/"):
                raise HarnessError(
                    f"fanout destination must start with {marker}/: {destination}"
                )
        elif marker in destination:
            raise HarnessError(
                f"destination uses {marker} without fanout: {destination}"
            )
        layer = raw.get("layer")
        if layer not in {"core", "profile"}:
            raise HarnessError(f"invalid layer for {destination}: {layer!r}")
        profile = raw.get("profile")
        if layer == "core" and profile is not None:
            raise HarnessError(f"core file {destination} may not declare a profile")
        if layer == "profile" and not isinstance(profile, str):
            raise HarnessError(f"profile file {destination} must declare a profile")
        if schema == 2 and layer == "profile" and not PROFILE_NAME.fullmatch(profile):
            raise HarnessError(
                f"invalid profile name for {destination}: {profile!r} "
                "(want family/variant or plain lowercase name)"
            )
        templated = raw.get("templated", False)
        if not isinstance(templated, bool):
            raise HarnessError(f"templated flag for {destination} must be boolean")
        executable = raw.get("executable", False)
        if not isinstance(executable, bool):
            raise HarnessError(f"executable flag for {destination} must be boolean")
        sha256 = raw.get("sha256")
        if not isinstance(sha256, str) or not sha256.startswith("sha256:"):
            raise HarnessError(f"invalid source digest for {destination}")
        source_path = root / source
        if not source_path.is_file() or source_path.is_symlink():
            raise HarnessError(f"release source is missing or not a regular file: {source}")
        actual = digest_file(source_path)
        if actual != sha256:
            raise HarnessError(
                f"source digest mismatch for {source}: expected {sha256}, got {actual}"
            )
        expansions: list[tuple[str, str | None, dict[str, str] | None]]
        if fanout:
            expansions = []
            for target in targets:
                expanded = normalized_relative(
                    destination.replace(marker, target.root, 1),
                    f"files[{index}].destination for target {target.name}",
                )
                overlay = dict(target.params)
                overlay[TARGET_ROOT_PARAM] = target.root
                expansions.append((expanded, target.name, overlay))
        else:
            expansions = [(destination, None, None)]
        for expanded, target_name, overlay in expansions:
            if expanded == LOCK_NAME:
                raise HarnessError("release may not own the project lock")
            existing = destinations.get(expanded)
            if existing is not None:
                existing_layer, existing_profile = existing
                same_family_variants = (
                    schema == 2
                    and existing_layer == "profile"
                    and layer == "profile"
                    and existing_profile != profile
                    and profile_family(existing_profile) is not None
                    and profile_family(existing_profile) == profile_family(profile)
                )
                if not same_family_variants:
                    raise HarnessError(f"duplicate destination: {expanded}")
            else:
                destinations[expanded] = (str(layer), profile)
            files.append(
                ReleaseFile(
                    source,
                    expanded,
                    str(layer),
                    profile,
                    templated,
                    executable,
                    sha256,
                    target_name,
                    overlay,
                )
            )
    required = string_list(manifest.get("required_params", []), "required_params")
    if len(required) != len(set(required)):
        raise HarnessError("required_params contains duplicates")
    for name in required:
        if not PLACEHOLDER.fullmatch("{{" + name + "}}"):
            raise HarnessError(f"invalid parameter name: {name!r}")
    for entry in files:
        if entry.target is None:
            continue
        if not any(within_root(entry.destination, root) for root in managed_roots):
            raise HarnessError(
                f"fanout destination is outside every managed root: {entry.destination}"
            )
    declared_profiles = {
        entry.profile for entry in files if entry.layer == "profile" and entry.profile
    }
    profile_info = parse_profile_info(manifest, declared_profiles)
    if schema == 1 and profile_info:
        raise HarnessError("manifest profile_info requires schema_version 2")
    return Release(
        root,
        manifest,
        tuple(files),
        archive_sha256,
        targets=tuple(targets),
        managed_roots=tuple(managed_roots),
        profile_info=tuple(profile_info),
    )


def parse_assignments(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise HarnessError(f"{label} must use NAME=VALUE: {value!r}")
        name, content = value.split("=", 1)
        if not PLACEHOLDER.fullmatch("{{" + name + "}}"):
            raise HarnessError(f"invalid {label} name: {name!r}")
        if name in result:
            raise HarnessError(f"duplicate {label}: {name}")
        result[name] = content
    return result


def validate_parameters(release: Release, params: dict[str, str]) -> None:
    required = set(string_list(release.manifest.get("required_params", []), "required_params"))
    provided = set(params)
    if missing := sorted(required - provided):
        raise HarnessError(f"missing required parameter(s): {', '.join(missing)}")
    if unknown := sorted(provided - required):
        raise HarnessError(f"unknown parameter(s): {', '.join(unknown)}")


def render(source: bytes, entry: ReleaseFile, params: dict[str, str]) -> bytes:
    if not entry.templated:
        return source
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HarnessError(f"templated file is not UTF-8: {entry.source}") from exc
    effective = {**params, **(entry.params or {})}
    names = set(PLACEHOLDER.findall(text))
    if unknown := sorted(names - set(effective)):
        raise HarnessError(
            f"template {entry.source} contains undeclared parameters: {', '.join(unknown)}"
        )
    rendered = PLACEHOLDER.sub(lambda match: effective[match.group(1)], text)
    if PLACEHOLDER.search(rendered):
        raise HarnessError(f"unresolved template parameter in {entry.source}")
    return rendered.encode("utf-8")


def selected_targets(release: Release, targets: Iterable[str]) -> set[str]:
    declared = {target.name for target in release.targets}
    chosen = set(targets)
    if unknown := sorted(chosen - declared):
        raise HarnessError(f"unknown target(s): {', '.join(unknown)}")
    return chosen


def selected_files(
    release: Release, profiles: Iterable[str], targets: Iterable[str] = ()
) -> list[ReleaseFile]:
    chosen = set(profiles)
    declared = {
        entry.profile for entry in release.files if entry.layer == "profile" and entry.profile
    }
    if unknown := sorted(chosen - declared):
        raise HarnessError(f"unknown profile(s): {', '.join(unknown)}")
    by_family: dict[str, list[str]] = {}
    for name in sorted(chosen):
        family = profile_family(name)
        if family:
            by_family.setdefault(family, []).append(name)
    for family, names in by_family.items():
        if len(names) > 1:
            raise HarnessError(
                f"mutually exclusive profiles selected in family {family}: "
                + ", ".join(names)
            )
    chosen_targets = selected_targets(release, targets)
    return [
        entry
        for entry in release.files
        if (entry.layer == "core" or entry.profile in chosen)
        and (entry.target is None or entry.target in chosen_targets)
    ]


def matches_override(path: str, overrides: Iterable[str]) -> bool:
    return any(
        path == pattern.rstrip("/")
        or fnmatch.fnmatchcase(path, pattern)
        or (
            pattern.endswith("/**")
            and (path == pattern[:-3] or path.startswith(pattern[:-2]))
        )
        for pattern in overrides
    )


def validate_overrides(overrides: list[str]) -> None:
    for index, pattern in enumerate(overrides):
        if not pattern or pattern.startswith("/") or "\\" in pattern:
            raise HarnessError(f"unsafe override[{index}]: {pattern!r}")
        literal = pattern.replace("**", "x").replace("*", "x").replace("?", "x")
        normalized_relative(literal, f"override[{index}]")


def materialize(
    release: Release,
    profiles: list[str],
    params: dict[str, str],
    overrides: list[str],
    targets: list[str] | None = None,
) -> tuple[dict[str, bytes], dict[str, dict[str, object]]]:
    validate_parameters(release, params)
    validate_overrides(overrides)
    payload: dict[str, bytes] = {}
    receipt: dict[str, dict[str, object]] = {}
    for entry in selected_files(release, profiles, targets or []):
        if matches_override(entry.destination, overrides):
            continue
        data = render((release.root / entry.source).read_bytes(), entry, params)
        if entry.destination in payload:
            raise HarnessError(
                f"selected files collide on destination: {entry.destination}"
            )
        payload[entry.destination] = data
        receipt[entry.destination] = {
            "origin": entry.source,
            "layer": entry.layer,
            "profile": entry.profile,
            "rendered": entry.templated,
            "executable": entry.executable,
            "sha256": digest_bytes(data),
        }
        if entry.target is not None:
            receipt[entry.destination]["target"] = entry.target
    return payload, receipt


def safe_project(raw: str) -> Path:
    project = Path(raw).resolve()
    if not project.is_dir():
        raise HarnessError(f"project directory does not exist: {project}")
    return project


def safe_destination(project: Path, destination: str) -> Path:
    path = project / normalized_relative(destination, "destination")
    if not path.resolve().is_relative_to(project):
        raise HarnessError(f"destination escapes project: {destination}")
    cursor = project
    for part in PurePosixPath(destination).parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise HarnessError(f"destination traverses symlink: {destination}")
    if path.is_symlink():
        raise HarnessError(f"destination is a symlink: {destination}")
    return path


def load_lock(project: Path) -> dict[str, object]:
    lock = read_json(project / LOCK_NAME, "project lock")
    if lock.get("schema_version") != 1:
        raise HarnessError("unsupported project lock schema")
    if not isinstance(lock.get("files"), dict):
        raise HarnessError("project lock files must be an object")
    return lock


def lock_settings(
    lock: dict[str, object],
) -> tuple[list[str], dict[str, str], list[str], list[str]]:
    profiles = string_list(lock.get("profiles", []), "lock profiles")
    overrides = string_list(lock.get("overrides", []), "lock overrides")
    targets = string_list(lock.get("targets", []), "lock targets")
    managed = string_list(lock.get("managed_roots", []), "lock managed_roots")
    raw_params = lock.get("params", {})
    if not isinstance(raw_params, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in raw_params.items()
    ):
        raise HarnessError("lock params must be a string-to-string object")
    validate_overrides(overrides)
    return profiles, dict(raw_params), overrides, targets, managed


def drift(project: Path, lock: dict[str, object]) -> list[tuple[str, str, str | None, str | None]]:
    raw_files = lock["files"]
    assert isinstance(raw_files, dict)
    findings: list[tuple[str, str, str | None, str | None]] = []
    for raw_path, metadata in sorted(raw_files.items()):
        path = normalized_relative(raw_path, "lock file path")
        if not isinstance(metadata, dict):
            raise HarnessError(f"lock metadata for {path} must be an object")
        expected = metadata.get("sha256")
        if not isinstance(expected, str) or not expected.startswith("sha256:"):
            raise HarnessError(f"lock digest for {path} is invalid")
        destination = safe_destination(project, path)
        if not destination.exists():
            findings.append(("missing", path, expected, None))
        elif not destination.is_file():
            findings.append(("changed", path, expected, "not-a-regular-file"))
        else:
            actual = digest_file(destination)
            if actual != expected:
                findings.append(("changed", path, expected, actual))
            expected_executable = metadata.get("executable", False)
            if not isinstance(expected_executable, bool):
                raise HarnessError(f"lock executable flag for {path} is invalid")
            actual_executable = bool(destination.stat().st_mode & 0o111)
            if actual_executable != expected_executable:
                findings.append(
                    (
                        "mode",
                        path,
                        "executable" if expected_executable else "non-executable",
                        "executable" if actual_executable else "non-executable",
                    )
                )
    return findings


def build_lock(
    source: str,
    version: str,
    release_sha256: str,
    profiles: list[str],
    params: dict[str, str],
    overrides: list[str],
    receipt: dict[str, dict[str, object]],
    targets: list[str] | None = None,
    managed_roots: Iterable[str] | None = None,
) -> dict[str, object]:
    lock: dict[str, object] = {
        "schema_version": 1,
        "source": source,
        "version": version,
        "release_sha256": release_sha256,
        "workflow_ref": version,
        "profiles": sorted(profiles),
        "params": dict(sorted(params.items())),
        "overrides": sorted(overrides),
        "files": dict(sorted(receipt.items())),
    }
    if targets:
        lock["targets"] = sorted(targets)
    if managed_roots:
        lock["managed_roots"] = sorted(managed_roots)
    return lock


def apply_transaction(
    project: Path,
    payload: dict[str, bytes],
    new_lock: dict[str, object],
    old_lock: dict[str, object] | None,
    adopt_existing: bool,
    prune: Iterable[str] = (),
    managed_roots: Iterable[str] = (),
) -> None:
    if adopt_existing:
        mismatches = []
        receipt_files = new_lock.get("files")
        if not isinstance(receipt_files, dict):
            raise HarnessError("new lock files are invalid")
        for destination, data in payload.items():
            path = safe_destination(project, destination)
            metadata = receipt_files.get(destination)
            expected_executable = (
                metadata.get("executable", False) if isinstance(metadata, dict) else False
            )
            mode_matches = path.is_file() and bool(path.stat().st_mode & 0o111) == bool(
                expected_executable
            )
            if not path.is_file() or path.read_bytes() != data or not mode_matches:
                mismatches.append(destination)
        if mismatches:
            raise HarnessError(
                "adopt-existing bytes differ from release: " + ", ".join(mismatches)
            )
        write_json(project / LOCK_NAME, new_lock)
        return

    stage = Path(tempfile.mkdtemp(prefix=".harness-stage-", dir=project))
    backup = Path(tempfile.mkdtemp(prefix=".harness-backup-", dir=project))
    touched: list[str] = []
    try:
        for destination, data in payload.items():
            staged = stage / destination
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(data)
            receipt_files = new_lock.get("files")
            assert isinstance(receipt_files, dict)
            metadata = receipt_files[destination]
            assert isinstance(metadata, dict)
            staged.chmod(0o755 if metadata.get("executable", False) else 0o644)
        write_json(stage / LOCK_NAME, new_lock)

        old_paths: set[str] = set()
        if old_lock:
            raw = old_lock.get("files", {})
            if isinstance(raw, dict):
                old_paths = set(raw)
        removals = sorted((old_paths | set(prune)) - set(payload))
        self_updates = [
            path for path in payload if PurePosixPath(path).name == "harness.py"
        ]
        regular = sorted(set(payload) - set(self_updates))
        order = regular + sorted(self_updates)
        for destination in order + removals + [LOCK_NAME]:
            target = (
                project / LOCK_NAME
                if destination == LOCK_NAME
                else safe_destination(project, destination)
            )
            saved = backup / destination
            if target.exists():
                if not target.is_file() or target.is_symlink():
                    raise HarnessError(f"refusing to replace non-regular path: {destination}")
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            touched.append(destination)
            if destination in removals:
                target.unlink(missing_ok=True)
                continue
            staged = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
        prune_empty_directories(project, managed_roots)
    except Exception:
        for destination in reversed(touched):
            target = project / destination
            saved = backup / destination
            if saved.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(saved, target)
            elif target.exists() and target.is_file():
                target.unlink()
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def from_directory(path: str, version: str) -> Release:
    root = Path(path).resolve()
    if not root.is_dir():
        raise HarnessError(f"release directory does not exist: {root}")
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise HarnessError(f"release directory lacks {MANIFEST_NAME}")
    tree_digest = digest_file(manifest_path)
    return parse_release(root, version, tree_digest)


def parse_source_repo(source: str) -> tuple[str, str]:
    prefix = "https://github.com/"
    if not source.startswith(prefix):
        raise HarnessError("network source must be an https://github.com/OWNER/REPO URL")
    parts = source[len(prefix) :].strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise HarnessError("network source must name exactly OWNER/REPO")
    return parts[0], parts[1].removesuffix(".git")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not forward a GitHub token to a release object's storage host."""

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> urllib.request.Request | None:
        redirected = super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )
        if redirected is None:
            return None
        old_host = urllib.parse.urlsplit(request.full_url).netloc
        new_host = urllib.parse.urlsplit(new_url).netloc
        if old_host != new_host:
            redirected.remove_header("Authorization")
        return redirected


def request_headers(accept: str) -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": "gov-harness/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get(TOKEN_ENV)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def open_request(url: str, accept: str) -> object:
    request = urllib.request.Request(url, headers=request_headers(accept))
    opener = urllib.request.build_opener(SafeRedirectHandler())
    return opener.open(request, timeout=30)


def download(url: str, destination: Path, accept: str = "application/octet-stream") -> None:
    request = urllib.request.Request(url, headers=request_headers(accept))
    opener = urllib.request.build_opener(SafeRedirectHandler())
    try:
        with opener.open(request, timeout=30) as response:
            with destination.open("wb") as stream:
                shutil.copyfileobj(response, stream)
    except (OSError, urllib.error.URLError) as exc:
        raise HarnessError(f"download failed for {url}: {exc}") from exc


def private_release_assets(owner: str, repo: str, version: str) -> dict[str, str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{version}"
    try:
        with open_request(url, "application/vnd.github+json") as response:
            metadata = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"cannot resolve private release metadata: {exc}") from exc
    assets = metadata.get("assets") if isinstance(metadata, dict) else None
    if not isinstance(assets, list):
        raise HarnessError("private release metadata has no asset list")
    result: dict[str, str] = {}
    for asset in assets:
        if isinstance(asset, dict) and isinstance(asset.get("name"), str):
            api_url = asset.get("url")
            if isinstance(api_url, str):
                result[asset["name"]] = api_url
    return result


def safe_extract(archive: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or member.issym()
                    or member.islnk()
                    or not (member.isfile() or member.isdir())
                ):
                    raise HarnessError(f"unsafe archive member: {member.name}")
            for member in members:
                target = destination / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise HarnessError(f"cannot read archive member: {member.name}")
                with source, target.open("wb") as stream:
                    shutil.copyfileobj(source, stream)
                target.chmod(member.mode & 0o777)
    except (OSError, tarfile.TarError) as exc:
        raise HarnessError(f"cannot extract release archive: {exc}") from exc


def from_network(source: str, version: str) -> Release:
    owner, repo = parse_source_repo(source)
    temporary = Path(tempfile.mkdtemp(prefix="gov-harness-release-"))
    archive_name = f"gov-harness-{version}.tar.gz"
    base = f"https://github.com/{owner}/{repo}/releases/download/{version}"
    archive = temporary / archive_name
    sums = temporary / "SHA256SUMS"
    try:
        if os.environ.get(TOKEN_ENV):
            assets = private_release_assets(owner, repo, version)
            for name, destination in ((archive_name, archive), ("SHA256SUMS", sums)):
                if name not in assets:
                    raise HarnessError(f"release does not contain asset {name}")
                download(assets[name], destination)
        else:
            download(f"{base}/{archive_name}", archive)
            download(f"{base}/SHA256SUMS", sums)
        expected: str | None = None
        for line in sums.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*") == archive_name:
                expected = "sha256:" + parts[0].lower()
        if expected is None:
            raise HarnessError(f"SHA256SUMS does not name {archive_name}")
        actual = digest_file(archive)
        if actual != expected:
            raise HarnessError(
                f"release archive digest mismatch: expected {expected}, got {actual}"
            )
        extracted = temporary / "release-root"
        extracted.mkdir()
        safe_extract(archive, extracted)
        release = parse_release(extracted, version, actual)
        return Release(
            release.root,
            release.manifest,
            release.files,
            release.archive_sha256,
            cleanup=temporary,
            targets=release.targets,
            managed_roots=release.managed_roots,
            profile_info=release.profile_info,
        )
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def acquire_release(source: str, version: str, from_dir: str | None) -> Release:
    return from_directory(from_dir, version) if from_dir else from_network(source, version)


def cleanup_release(release: Release | None) -> None:
    if release and release.cleanup:
        shutil.rmtree(release.cleanup, ignore_errors=True)


def print_drift(findings: list[tuple[str, str, str | None, str | None]]) -> None:
    for kind, path, expected, actual in findings:
        print(f"{kind}: {path} expected={expected} actual={actual}")


def command_init(args: argparse.Namespace) -> int:
    project = safe_project(args.project)
    old_lock: dict[str, object] | None = None
    if (project / LOCK_NAME).exists():
        if not args.reinstall:
            raise HarnessError(f"{LOCK_NAME} already exists; use sync or --reinstall")
        old_lock = load_lock(project)
    params = parse_assignments(args.param, "parameter")
    release: Release | None = None
    try:
        release = acquire_release(args.source, args.to, args.from_dir)
        targets = args.target or [target.name for target in release.targets]
        payload, receipt = materialize(
            release, args.profile, params, args.override, targets
        )
        lock = build_lock(
            args.source,
            args.to,
            release.archive_sha256,
            args.profile,
            params,
            args.override,
            receipt,
            targets,
            release.managed_roots,
        )
        prune = stray_files(project, release.managed_roots, payload, args.override)
        for path in prune:
            print(f"pruning unmanaged file in a managed root: {path}")
        apply_transaction(
            project,
            payload,
            lock,
            old_lock,
            args.adopt_existing,
            prune,
            release.managed_roots,
        )
        verb = "reinstalled" if old_lock else "installed"
        print(f"{verb} {args.to}: {len(payload)} governed file(s), {len(prune)} pruned")
        return 0
    finally:
        cleanup_release(release)


def prompt_line(message: str) -> str:
    try:
        return input(message)
    except EOFError as exc:
        raise HarnessError("selection aborted: end of input") from exc


def resolve_choices(
    choices: list[str],
    families: dict[str, list[str]],
    standalone: list[str],
) -> list[str]:
    chosen: list[str] = []
    for raw in choices:
        if "=" in raw:
            family, _, variant = raw.partition("=")
            if family not in families:
                raise HarnessError(f"unknown profile family: {family}")
            full = variant if "/" in variant else f"{family}/{variant}"
            if full not in families[family]:
                raise HarnessError(
                    f"unknown variant {variant!r} in family {family} "
                    f"(have: {', '.join(v.split('/', 1)[1] for v in families[family])})"
                )
            chosen.append(full)
        else:
            if raw not in standalone:
                raise HarnessError(f"unknown standalone profile: {raw}")
            chosen.append(raw)
    return chosen


def menu_choices(
    families: dict[str, list[str]],
    standalone: list[str],
    info: dict[str, str],
) -> list[str]:
    chosen: list[str] = []
    print("Выбор технологического стека (0 или Enter — пропустить семейство):")
    for family, variants in families.items():
        print(f"\n[{family}]")
        for index, name in enumerate(variants, 1):
            label = name.split("/", 1)[1]
            description = info.get(name, "")
            print(f"  {index}. {label}" + (f" — {description}" if description else ""))
        while True:
            answer = prompt_line(f"{family} [0-{len(variants)}]: ").strip()
            if answer in ("", "0"):
                break
            if answer.isdigit() and 1 <= int(answer) <= len(variants):
                chosen.append(variants[int(answer) - 1])
                break
            print(f"  введите число от 0 до {len(variants)}")
    for name in standalone:
        description = info.get(name, "")
        suffix = f" — {description}" if description else ""
        answer = prompt_line(f"\nвключить {name}{suffix}? [y/N]: ").strip().lower()
        if answer in ("y", "yes", "д", "да"):
            chosen.append(name)
    return chosen


def command_select(args: argparse.Namespace) -> int:
    release: Release | None = None
    try:
        release = acquire_release(args.source, args.to, args.from_dir)
        declared = sorted(
            {
                entry.profile
                for entry in release.files
                if entry.layer == "profile" and entry.profile
            }
        )
        if not declared:
            raise HarnessError("release declares no profiles; nothing to select")
        families: dict[str, list[str]] = {}
        standalone: list[str] = []
        for name in declared:
            family = profile_family(name)
            if family:
                families.setdefault(family, []).append(name)
            else:
                standalone.append(name)
        info = dict(release.profile_info)
        if args.choose:
            chosen = resolve_choices(args.choose, families, standalone)
        else:
            chosen = menu_choices(families, standalone, info)
        print("\nвыбранные профили: " + (", ".join(chosen) if chosen else "(нет)"))
        command = ["harness.py", "init", "--source", args.source, "--to", args.to]
        for name in chosen:
            command += ["--profile", name]
        if args.reinstall:
            command.append("--reinstall")
        print("команда: " + " ".join(command))
        if args.print_only:
            return 0
        init_args = argparse.Namespace(
            project=args.project,
            source=args.source,
            to=args.to,
            profile=chosen,
            target=args.target,
            param=args.param,
            override=args.override,
            from_dir=args.from_dir,
            adopt_existing=False,
            reinstall=args.reinstall,
        )
        return command_init(init_args)
    finally:
        cleanup_release(release)


def command_sync(args: argparse.Namespace) -> int:
    project = safe_project(args.project)
    old_lock = load_lock(project)
    source = old_lock.get("source")
    if not isinstance(source, str):
        raise HarnessError("lock source is invalid")
    profiles, params, overrides, targets, _managed = lock_settings(old_lock)
    current_drift = drift(project, old_lock)
    release: Release | None = None
    try:
        release = acquire_release(source, args.to, args.from_dir)
        if not targets:
            targets = [target.name for target in release.targets]
        payload, receipt = materialize(release, profiles, params, overrides, targets)
        old_files = old_lock.get("files")
        if not isinstance(old_files, dict):
            raise HarnessError("lock files are invalid")
        prune = stray_files(project, release.managed_roots, payload, overrides)
        collisions = []
        for path, data in payload.items():
            destination = safe_destination(project, path)
            if path not in old_files and destination.exists():
                identical = destination.is_file() and destination.read_bytes() == data
                if not identical and path not in prune:
                    collisions.append(path)
        if collisions and not args.force_theirs:
            raise HarnessError(
                "new release destination collides with an unmanaged local path: "
                + ", ".join(sorted(collisions))
                + "; move it, adopt it upstream, or explicitly --force-theirs"
            )
        unexplained = []
        for finding in current_drift:
            _, path, _, _ = finding
            destination = safe_destination(project, path)
            converged = (
                path in payload
                and destination.is_file()
                and destination.read_bytes() == payload[path]
            )
            if not converged:
                unexplained.append(finding)
        if unexplained and not args.force_theirs:
            print_drift(unexplained)
            raise HarnessError(
                "local drift blocks sync; use adopt or explicitly --force-theirs"
            )
        new_lock = build_lock(
            source,
            args.to,
            release.archive_sha256,
            profiles,
            params,
            overrides,
            receipt,
            targets,
            release.managed_roots,
        )
        for path in prune:
            print(f"pruning unmanaged file in a managed root: {path}")
        if old_lock == new_lock and not current_drift and not prune:
            print(f"already at {args.to}; empty diff")
            return 0
        apply_transaction(
            project,
            payload,
            new_lock,
            old_lock,
            False,
            prune,
            release.managed_roots,
        )
        print(
            f"synced {old_lock.get('version')} -> {args.to}: "
            f"{len(payload)} file(s), {len(prune)} pruned"
        )
        return 0
    finally:
        cleanup_release(release)


def command_check(args: argparse.Namespace) -> int:
    project = safe_project(args.project)
    lock = load_lock(project)
    findings = drift(project, lock)
    print_drift(findings)
    _, _, overrides, _, managed = lock_settings(lock)
    raw_files = lock.get("files")
    keep = set(raw_files) if isinstance(raw_files, dict) else set()
    strays = stray_files(project, managed, keep, overrides)
    for path in strays:
        print(f"stray: {path} expected=absent actual=unmanaged")
    if findings or strays:
        print(f"drift: {len(findings)} file(s), stray: {len(strays)} file(s)")
        return 2
    print("harness clean")
    return 0


def command_diff(args: argparse.Namespace) -> int:
    return command_check(args)


def git_output(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=project,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HarnessError(f"git failed: {exc}") from exc


def command_adopt(args: argparse.Namespace) -> int:
    project = safe_project(args.project)
    lock = load_lock(project)
    raw_files = lock["files"]
    assert isinstance(raw_files, dict)
    requested = [normalized_relative(path, "adopt path") for path in args.paths]
    if not requested:
        raise HarnessError("adopt requires at least one governed path")
    for path in requested:
        if path not in raw_files:
            raise HarnessError(f"adopt path is not receipt-owned: {path}")
        metadata = raw_files[path]
        if not isinstance(metadata, dict):
            raise HarnessError(f"lock metadata for {path} is invalid")
        if metadata.get("rendered") is True:
            raise HarnessError(
                f"adopt cannot reverse a rendered template automatically: {path}"
            )
        normalized_relative(metadata.get("origin"), f"origin for {path}")
        safe_destination(project, path)
    commit = git_output(project, "rev-parse", "HEAD")
    if commit.returncode != 0:
        raise HarnessError("adopt requires a Git repository with a HEAD commit")
    base_commit = commit.stdout.strip()
    chunks: list[str] = []
    mappings: list[dict[str, str]] = []
    for path in requested:
        metadata = raw_files[path]
        assert isinstance(metadata, dict)
        origin = normalized_relative(metadata.get("origin"), f"origin for {path}")
        mappings.append({"destination": path, "origin": origin})
        before_result = git_output(project, "show", f"HEAD:{path}")
        before = before_result.stdout.splitlines(keepends=True) if before_result.returncode == 0 else []
        destination = safe_destination(project, path)
        after = (
            destination.read_text(encoding="utf-8").splitlines(keepends=True)
            if destination.is_file()
            else []
        )
        chunks.extend(
            difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{origin}",
                tofile=f"b/{origin}",
            )
        )
    if not chunks:
        raise HarnessError("adopt found no content difference against Git HEAD")
    output_root = project / ADOPT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(
        (base_commit + "\0" + "\0".join(sorted(requested))).encode("utf-8")
    ).hexdigest()[:12]
    patch_name = f"adopt-{identity}.patch"
    metadata_name = f"adopt-{identity}.json"
    patch_path = output_root / patch_name
    metadata_path = output_root / metadata_name
    patch_path.write_text("".join(chunks), encoding="utf-8")
    metadata = {
        "schema_version": 1,
        "source": lock.get("source"),
        "installed_version": lock.get("version"),
        "base_commit": base_commit,
        "mappings": sorted(mappings, key=lambda item: item["destination"]),
        "patch": patch_name,
        "patch_sha256": digest_file(patch_path),
    }
    write_json(metadata_path, metadata)
    print(relative_to_project(metadata_path, project))
    print(relative_to_project(patch_path, project))
    return 0


def relative_to_project(path: Path, project: Path) -> str:
    return path.relative_to(project).as_posix()


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=".", help="target project directory")
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", parents=[common])
    init.add_argument("--source", required=True)
    init.add_argument("--to", required=True)
    init.add_argument("--profile", action="append", default=[])
    init.add_argument(
        "--target",
        action="append",
        default=[],
        help="install only these manifest targets (default: all declared)",
    )
    init.add_argument("--param", action="append", default=[])
    init.add_argument("--override", action="append", default=[])
    init.add_argument("--from-dir")
    init.add_argument("--adopt-existing", action="store_true")
    init.add_argument(
        "--reinstall",
        action="store_true",
        help="reconcile an already-installed project instead of refusing",
    )
    init.set_defaults(handler=command_init)

    select = commands.add_parser(
        "select",
        parents=[common],
        help="interactive stack menu: pick one variant per profile family, then install",
    )
    select.add_argument("--source", required=True)
    select.add_argument("--to", required=True)
    select.add_argument("--target", action="append", default=[])
    select.add_argument("--param", action="append", default=[])
    select.add_argument("--override", action="append", default=[])
    select.add_argument("--from-dir")
    select.add_argument("--reinstall", action="store_true")
    select.add_argument(
        "--choose",
        action="append",
        default=[],
        help="non-interactive: family=variant (repeatable) or a standalone profile name",
    )
    select.add_argument("--print-only", action="store_true")
    select.set_defaults(handler=command_select)

    sync = commands.add_parser("sync", parents=[common])
    sync.add_argument("--to", required=True)
    sync.add_argument("--from-dir")
    sync.add_argument("--force-theirs", action="store_true")
    sync.set_defaults(handler=command_sync)

    check = commands.add_parser("check", parents=[common])
    check.set_defaults(handler=command_check)

    diff = commands.add_parser("diff", parents=[common])
    diff.set_defaults(handler=command_diff)

    adopt = commands.add_parser("adopt", parents=[common])
    adopt.add_argument("paths", nargs="+")
    adopt.set_defaults(handler=command_adopt)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except HarnessError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("REFUSED: interrupted", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
