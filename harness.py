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


class HarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseFile:
    source: str
    destination: str
    layer: str
    profile: str | None
    templated: bool
    sha256: str


@dataclass(frozen=True)
class Release:
    root: Path
    manifest: dict[str, object]
    files: tuple[ReleaseFile, ...]
    archive_sha256: str
    cleanup: Path | None = None


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


def parse_release(root: Path, expected_version: str, archive_sha256: str) -> Release:
    manifest = read_json(root / MANIFEST_NAME, "release manifest")
    if manifest.get("schema_version") != 1:
        raise HarnessError("unsupported release manifest schema")
    if manifest.get("version") != expected_version:
        raise HarnessError(
            f"release version mismatch: expected {expected_version}, got {manifest.get('version')}"
        )
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise HarnessError("release manifest files must be a non-empty list")
    files: list[ReleaseFile] = []
    destinations: set[str] = set()
    for index, raw in enumerate(raw_files):
        if not isinstance(raw, dict):
            raise HarnessError(f"manifest files[{index}] must be an object")
        source = normalized_relative(raw.get("source"), f"files[{index}].source")
        destination = normalized_relative(
            raw.get("destination"), f"files[{index}].destination"
        )
        if destination == LOCK_NAME:
            raise HarnessError("release may not own the project lock")
        if destination in destinations:
            raise HarnessError(f"duplicate destination: {destination}")
        destinations.add(destination)
        layer = raw.get("layer")
        if layer not in {"core", "profile"}:
            raise HarnessError(f"invalid layer for {destination}: {layer!r}")
        profile = raw.get("profile")
        if layer == "core" and profile is not None:
            raise HarnessError(f"core file {destination} may not declare a profile")
        if layer == "profile" and not isinstance(profile, str):
            raise HarnessError(f"profile file {destination} must declare a profile")
        templated = raw.get("templated", False)
        if not isinstance(templated, bool):
            raise HarnessError(f"templated flag for {destination} must be boolean")
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
        files.append(
            ReleaseFile(source, destination, str(layer), profile, templated, sha256)
        )
    required = string_list(manifest.get("required_params", []), "required_params")
    if len(required) != len(set(required)):
        raise HarnessError("required_params contains duplicates")
    for name in required:
        if not PLACEHOLDER.fullmatch("{{" + name + "}}"):
            raise HarnessError(f"invalid parameter name: {name!r}")
    return Release(root, manifest, tuple(files), archive_sha256)


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
    names = set(PLACEHOLDER.findall(text))
    if unknown := sorted(names - set(params)):
        raise HarnessError(
            f"template {entry.source} contains undeclared parameters: {', '.join(unknown)}"
        )
    rendered = PLACEHOLDER.sub(lambda match: params[match.group(1)], text)
    if PLACEHOLDER.search(rendered):
        raise HarnessError(f"unresolved template parameter in {entry.source}")
    return rendered.encode("utf-8")


def selected_files(release: Release, profiles: Iterable[str]) -> list[ReleaseFile]:
    chosen = set(profiles)
    declared = {
        entry.profile for entry in release.files if entry.layer == "profile" and entry.profile
    }
    if unknown := sorted(chosen - declared):
        raise HarnessError(f"unknown profile(s): {', '.join(unknown)}")
    return [
        entry
        for entry in release.files
        if entry.layer == "core" or entry.profile in chosen
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
) -> tuple[dict[str, bytes], dict[str, dict[str, object]]]:
    validate_parameters(release, params)
    validate_overrides(overrides)
    payload: dict[str, bytes] = {}
    receipt: dict[str, dict[str, object]] = {}
    for entry in selected_files(release, profiles):
        if matches_override(entry.destination, overrides):
            continue
        data = render((release.root / entry.source).read_bytes(), entry, params)
        payload[entry.destination] = data
        receipt[entry.destination] = {
            "origin": entry.source,
            "layer": entry.layer,
            "profile": entry.profile,
            "rendered": entry.templated,
            "sha256": digest_bytes(data),
        }
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


def lock_settings(lock: dict[str, object]) -> tuple[list[str], dict[str, str], list[str]]:
    profiles = string_list(lock.get("profiles", []), "lock profiles")
    overrides = string_list(lock.get("overrides", []), "lock overrides")
    raw_params = lock.get("params", {})
    if not isinstance(raw_params, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in raw_params.items()
    ):
        raise HarnessError("lock params must be a string-to-string object")
    validate_overrides(overrides)
    return profiles, dict(raw_params), overrides


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
    return findings


def build_lock(
    source: str,
    version: str,
    release_sha256: str,
    profiles: list[str],
    params: dict[str, str],
    overrides: list[str],
    receipt: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
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


def apply_transaction(
    project: Path,
    payload: dict[str, bytes],
    new_lock: dict[str, object],
    old_lock: dict[str, object] | None,
    adopt_existing: bool,
) -> None:
    if adopt_existing:
        mismatches = []
        for destination, data in payload.items():
            path = safe_destination(project, destination)
            if not path.is_file() or path.read_bytes() != data:
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
        write_json(stage / LOCK_NAME, new_lock)

        old_paths: set[str] = set()
        if old_lock:
            raw = old_lock.get("files", {})
            if isinstance(raw, dict):
                old_paths = set(raw)
        removals = sorted(old_paths - set(payload))
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
    if (project / LOCK_NAME).exists():
        raise HarnessError(f"{LOCK_NAME} already exists; use sync")
    params = parse_assignments(args.param, "parameter")
    release: Release | None = None
    try:
        release = acquire_release(args.source, args.to, args.from_dir)
        payload, receipt = materialize(release, args.profile, params, args.override)
        lock = build_lock(
            args.source,
            args.to,
            release.archive_sha256,
            args.profile,
            params,
            args.override,
            receipt,
        )
        apply_transaction(project, payload, lock, None, args.adopt_existing)
        print(f"installed {args.to}: {len(payload)} governed file(s)")
        return 0
    finally:
        cleanup_release(release)


def command_sync(args: argparse.Namespace) -> int:
    project = safe_project(args.project)
    old_lock = load_lock(project)
    source = old_lock.get("source")
    if not isinstance(source, str):
        raise HarnessError("lock source is invalid")
    profiles, params, overrides = lock_settings(old_lock)
    current_drift = drift(project, old_lock)
    release: Release | None = None
    try:
        release = acquire_release(source, args.to, args.from_dir)
        payload, receipt = materialize(release, profiles, params, overrides)
        old_files = old_lock.get("files")
        if not isinstance(old_files, dict):
            raise HarnessError("lock files are invalid")
        collisions = []
        for path, data in payload.items():
            destination = safe_destination(project, path)
            if path not in old_files and destination.exists():
                identical = destination.is_file() and destination.read_bytes() == data
                if not identical:
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
        )
        if old_lock == new_lock and not current_drift:
            print(f"already at {args.to}; empty diff")
            return 0
        apply_transaction(project, payload, new_lock, old_lock, False)
        print(f"synced {old_lock.get('version')} -> {args.to}: {len(payload)} file(s)")
        return 0
    finally:
        cleanup_release(release)


def command_check(args: argparse.Namespace) -> int:
    project = safe_project(args.project)
    findings = drift(project, load_lock(project))
    print_drift(findings)
    if findings:
        print(f"drift: {len(findings)} file(s)")
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
    init.add_argument("--param", action="append", default=[])
    init.add_argument("--override", action="append", default=[])
    init.add_argument("--from-dir")
    init.add_argument("--adopt-existing", action="store_true")
    init.set_defaults(handler=command_init)

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
