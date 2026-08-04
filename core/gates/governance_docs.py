#!/usr/bin/env python3
"""Static governance-document gates.

The checker intentionally uses only the Python standard library.  It never
performs network I/O and it writes only the explicitly selected report file.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote


GATES = ("DOC-G1", "DOC-G2", "DOC-G4", "DOC-G5", "DOC-G6")
REQUIRED_METADATA = ("id", "class", "status", "owner", "updated", "sources")
ALLOWED_STATUS = {
    "state": {"active", "deprecated", "superseded"},
    "event": {"active", "sealed", "superseded"},
    "generated": {"current"},
}
LINK_PATTERN = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
REFERENCE_PATTERN = re.compile(r"^\s*\[[^\]]+]:\s*(\S+)")
HOME_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/[^\s`\"'<>)]*")


class ConfigurationError(RuntimeError):
    """The gate cannot run deterministically with the supplied configuration."""


@dataclass(frozen=True)
class Finding:
    gate: str
    path: str
    line: int
    message: str
    target: str | None = None


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def load_config(root: Path, config_arg: str) -> dict[str, object]:
    config_path = Path(config_arg)
    if not config_path.is_absolute():
        config_path = root / config_path
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(
            f"cannot load config {config_path}: {exc}; "
            "copy docs/governance/docs-policy.example.json and edit it"
        ) from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ConfigurationError("config must be an object with schema_version=1")
    return value


def string_list(config: dict[str, object], name: str) -> list[str]:
    value = config.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigurationError(f"{name} must be a list of strings")
    return value


def excluded(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def markdown_files(
    root: Path, entries: Iterable[str], exclude_patterns: Iterable[str]
) -> list[Path]:
    result: set[Path] = set()
    for entry in entries:
        candidate = root / entry
        if not candidate.exists():
            raise ConfigurationError(f"configured path does not exist: {entry}")
        paths = [candidate] if candidate.is_file() else candidate.rglob("*.md")
        for path in paths:
            if path.is_file() and path.suffix.lower() == ".md":
                rel = relative(path, root)
                if not excluded(rel, exclude_patterns):
                    result.add(path)
    return sorted(result)


def unfenced_lines(text: str) -> Iterable[tuple[int, str]]:
    in_fence = False
    marker = ""
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            current = stripped[:3]
            if not in_fence:
                in_fence, marker = True, current
            elif current == marker:
                in_fence = False
            continue
        if not in_fence:
            yield number, line


def clean_link_target(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    elif re.search(r"\s+[\"']", target):
        target = re.split(r"\s+[\"']", target, maxsplit=1)[0]
    target = unquote(target.strip())
    if not target or target.startswith("#"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target or any(char in target for char in ("{", "}", "*")):
        return None
    return target


def check_links(root: Path, config: dict[str, object]) -> list[Finding]:
    files = markdown_files(
        root,
        string_list(config, "link_roots"),
        string_list(config, "link_excludes"),
    )
    findings: list[Finding] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in unfenced_lines(text):
            targets = [match.group(1) for match in LINK_PATTERN.finditer(line)]
            reference = REFERENCE_PATTERN.match(line)
            if reference:
                targets.append(reference.group(1))
            for raw in targets:
                target = clean_link_target(raw)
                if target is None:
                    continue
                posix = PurePosixPath(target)
                candidates = (
                    [root / str(posix).lstrip("/")]
                    if target.startswith("/")
                    else [path.parent / str(posix), root / str(posix)]
                )
                valid_candidates = [
                    candidate
                    for candidate in candidates
                    if candidate.resolve().is_relative_to(root)
                ]
                if not any(candidate.exists() for candidate in valid_candidates):
                    findings.append(
                        Finding(
                            "DOC-G1",
                            relative(path, root),
                            number,
                            "unresolved relative Markdown reference",
                            target,
                        )
                    )
    return findings


def frontmatter(text: str) -> tuple[dict[str, str], int] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values, end


def check_metadata(root: Path, config: dict[str, object]) -> list[Finding]:
    files = markdown_files(
        root,
        string_list(config, "metadata_roots"),
        string_list(config, "metadata_excludes"),
    )
    baseline = config.get("legacy_missing_frontmatter_max")
    if not isinstance(baseline, int) or baseline < 0:
        raise ConfigurationError("legacy_missing_frontmatter_max must be a non-negative integer")
    findings: list[Finding] = []
    missing: list[Path] = []
    for path in files:
        parsed = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if parsed is None:
            missing.append(path)
            continue
        metadata, _ = parsed
        absent = [key for key in REQUIRED_METADATA if not metadata.get(key)]
        if absent:
            findings.append(
                Finding(
                    "DOC-G2",
                    relative(path, root),
                    1,
                    f"frontmatter is missing required fields: {', '.join(absent)}",
                )
            )
            continue
        doc_class = metadata["class"].lower()
        status = metadata["status"].lower()
        if doc_class not in ALLOWED_STATUS:
            findings.append(
                Finding(
                    "DOC-G2",
                    relative(path, root),
                    1,
                    f"unsupported lifecycle class: {doc_class}",
                )
            )
        elif status not in ALLOWED_STATUS[doc_class]:
            findings.append(
                Finding(
                    "DOC-G2",
                    relative(path, root),
                    1,
                    f"status {status!r} is invalid for class {doc_class!r}",
                )
            )
        if doc_class == "generated":
            absent_generated = [
                key for key in ("generator", "source_digest") if not metadata.get(key)
            ]
            if absent_generated:
                findings.append(
                    Finding(
                        "DOC-G2",
                        relative(path, root),
                        1,
                        "generated document is missing required fields: "
                        + ", ".join(absent_generated),
                    )
                )
        if doc_class == "event" and status == "sealed":
            for key in ("truth_as_of", "superseded_by"):
                if key not in metadata:
                    findings.append(
                        Finding(
                            "DOC-G2",
                            relative(path, root),
                            1,
                            f"sealed event is missing {key}",
                        )
                    )
        # A retired state document must name what replaced it. The field is
        # required, its answer is not: an explicit empty list records "retired,
        # nothing supersedes it", while a missing field records nothing at all.
        if doc_class == "state" and status in {"superseded", "deprecated"}:
            if not metadata.get("superseded_by"):
                findings.append(
                    Finding(
                        "DOC-G2",
                        relative(path, root),
                        1,
                        f"{status} state document must declare a non-empty "
                        "superseded_by (use [] to record that nothing replaces it)",
                    )
                )
    if len(missing) > baseline:
        sample = ", ".join(relative(path, root) for path in missing[:5])
        findings.append(
            Finding(
                "DOC-G2",
                ".",
                0,
                f"legacy frontmatter debt increased: {len(missing)} > {baseline}; sample: {sample}",
            )
        )
    return findings


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=check,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(f"git {' '.join(args)} failed: {exc}") from exc


def strip_mutable_seal_fields(text: str) -> str:
    parsed = frontmatter(text)
    if parsed is None:
        return text
    _, end = parsed
    lines = text.splitlines()
    kept = [lines[0]]
    skip_indented = False
    for line in lines[1:end]:
        if line and not line[0].isspace():
            key = line.split(":", 1)[0].strip()
            skip_indented = key in {"status", "superseded_by"}
            if skip_indented:
                continue
        elif skip_indented:
            continue
        kept.append(line)
    kept.extend(lines[end:])
    return "\n".join(kept).rstrip() + "\n"


def check_seals(root: Path, config: dict[str, object], base: str | None) -> list[Finding]:
    if base is None:
        return []
    git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    scope = string_list(config, "seal_roots")
    changed = git(root, "diff", "--name-only", base, "--", *scope).stdout.splitlines()
    findings: list[Finding] = []
    for rel in changed:
        before_result = git(root, "show", f"{base}:{rel}", check=False)
        path = root / rel
        before = before_result.stdout if before_result.returncode == 0 else ""
        after = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        before_meta = frontmatter(before)
        after_meta = frontmatter(after)
        was_sealed = bool(
            before_meta
            and before_meta[0].get("class", "").lower() == "event"
            and before_meta[0].get("status", "").lower() == "sealed"
        )
        is_sealed = bool(
            after_meta
            and after_meta[0].get("class", "").lower() == "event"
            and after_meta[0].get("status", "").lower() == "sealed"
        )
        if was_sealed and strip_mutable_seal_fields(before) != strip_mutable_seal_fields(after):
            findings.append(
                Finding(
                    "DOC-G4",
                    rel,
                    0,
                    "sealed event changed outside status/superseded_by",
                )
            )
    return findings


def check_portability(root: Path, config: dict[str, object]) -> list[Finding]:
    files = markdown_files(
        root,
        string_list(config, "portability_roots"),
        string_list(config, "portability_excludes"),
    )
    owner = config.get("environment_owner")
    if not isinstance(owner, str):
        raise ConfigurationError("environment_owner must be a repository-relative path")
    findings: list[Finding] = []
    for path in files:
        rel = relative(path, root)
        if rel == owner:
            continue
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            if HOME_PATH_PATTERN.search(line):
                findings.append(
                    Finding(
                        "DOC-G5",
                        rel,
                        number,
                        "machine-bound home path exists outside the environment owner",
                    )
                )
    return findings


def holds_content(path: Path) -> bool:
    """True when a candidate home actually carries specification documents."""
    return path.is_dir() and any(path.rglob("*.md"))


def check_spec_home(root: Path, config: dict[str, object]) -> tuple[list[Finding], str | None]:
    """DOC-G6 — a repository has exactly one populated specification home."""
    homes = string_list(config, "spec_homes")
    if not homes:
        return [], "DOC-G6: spec_homes is not configured"
    if len(set(homes)) != len(homes):
        raise ConfigurationError("spec_homes contains duplicates")
    declared = config.get("spec_home")
    if declared is not None and not isinstance(declared, str):
        raise ConfigurationError("spec_home must be a string when present")
    if declared is not None and declared not in homes:
        raise ConfigurationError(f"spec_home {declared!r} is not listed in spec_homes")

    populated: list[str] = []
    for home in homes:
        candidate = root / PurePosixPath(home)
        if not candidate.resolve().is_relative_to(root):
            raise ConfigurationError(f"spec_homes entry escapes the repository: {home}")
        if holds_content(candidate):
            populated.append(home)

    findings: list[Finding] = []
    if declared is None:
        if len(populated) > 1:
            findings.append(
                Finding(
                    "DOC-G6",
                    ".",
                    0,
                    "several specification homes hold content and none is "
                    f"declared: {', '.join(populated)}; set spec_home",
                )
            )
        return findings, None
    for home in populated:
        if home != declared:
            findings.append(
                Finding(
                    "DOC-G6",
                    home,
                    0,
                    "second specification home holds content; the declared "
                    f"home is {declared}",
                )
            )
    return findings, None


def write_report(
    output: Path,
    root: Path,
    mode: str,
    selected: list[str],
    skipped: list[str],
    findings: list[Finding],
) -> None:
    payload = {
        "schema_version": 1,
        "mode": mode,
        "root": str(root),
        "gates": selected,
        "skipped": skipped,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default="docs/governance/docs-policy.json")
    parser.add_argument("--mode", choices=("report", "block"), default="report")
    parser.add_argument("--gate", action="append", choices=GATES)
    parser.add_argument("--base", help="explicit Git base for DOC-G4")
    parser.add_argument("--output", default=".artifacts/governance/docs-report.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).resolve()
    try:
        config = load_config(root, args.config)
        selected = args.gate or list(GATES)
        skipped: list[str] = []
        findings: list[Finding] = []
        if "DOC-G1" in selected:
            findings.extend(check_links(root, config))
        if "DOC-G2" in selected:
            findings.extend(check_metadata(root, config))
        if "DOC-G4" in selected:
            if args.base is None:
                skipped.append("DOC-G4: explicit --base was not supplied")
            else:
                findings.extend(check_seals(root, config, args.base))
        if "DOC-G5" in selected:
            findings.extend(check_portability(root, config))
        if "DOC-G6" in selected:
            spec_findings, spec_skipped = check_spec_home(root, config)
            findings.extend(spec_findings)
            if spec_skipped is not None:
                skipped.append(spec_skipped)
        findings.sort(key=lambda item: (item.gate, item.path, item.line, item.message))
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        write_report(output, root, args.mode, selected, skipped, findings)
    except ConfigurationError as exc:
        print(f"CONFIG: {exc}", file=sys.stderr)
        return 2

    for item in findings:
        location = f"{item.path}:{item.line}" if item.line else item.path
        suffix = f" -> {item.target}" if item.target else ""
        print(f"{item.gate} {location}: {item.message}{suffix}")
    for item in skipped:
        print(f"SKIP {item}")
    print(f"governance docs: {len(findings)} finding(s), mode={args.mode}")
    return 1 if findings and args.mode == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
