#!/usr/bin/env python3
"""Validate the installed skill boundary and receipt ownership."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path, PurePosixPath


FRONTMATTER_KEY = re.compile(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$")


def safe_relative(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must stay inside the repository: {value}")
    return Path(*path.parts)


def load_object(path: Path, name: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"{name} must be an object with schema_version=1")
    return value


def frontmatter_keys(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    result: dict[str, str] = {}
    for line in lines[1:end]:
        match = FRONTMATTER_KEY.match(line)
        if match:
            result[match.group(1)] = (match.group(2) or "").strip()
    return result


def run(root: Path, policy: dict[str, object], lock: dict[str, object]) -> list[str]:
    skills_root = safe_relative(policy.get("skills_root"), "skills_root")
    configured = policy.get("skills")
    if not isinstance(configured, dict) or not all(
        isinstance(name, str) and layer in {"core", "profile", "local"}
        for name, layer in configured.items()
    ):
        raise ValueError("skills must map names to core, profile or local")
    actual_root = root / skills_root
    actual = {path.name for path in actual_root.iterdir() if path.is_dir()}
    expected = set(configured)
    findings = [
        f"unexpected installed skill: {name}" for name in sorted(actual - expected)
    ]
    findings.extend(
        f"missing installed skill: {name}" for name in sorted(expected - actual)
    )

    files = lock.get("files")
    overrides = lock.get("overrides")
    if not isinstance(files, dict) or not isinstance(overrides, list):
        raise ValueError("lock must contain files and overrides")
    for name, layer in sorted(configured.items()):
        skill_rel = (skills_root / name / "SKILL.md").as_posix()
        skill_path = root / skill_rel
        if not skill_path.is_file():
            continue
        metadata = frontmatter_keys(skill_path)
        if metadata.get("name") != name:
            findings.append(f"{skill_rel}: frontmatter name must be {name!r}")
        if "description" not in metadata:
            findings.append(f"{skill_rel}: frontmatter description is required")
        if layer == "local":
            if not any(
                isinstance(pattern, str) and fnmatch.fnmatchcase(skill_rel, pattern)
                for pattern in overrides
            ):
                findings.append(f"{skill_rel}: local skill is not covered by a lock override")
            if skill_rel in files:
                findings.append(f"{skill_rel}: local skill must not be receipt-owned")
        else:
            receipt = files.get(skill_rel)
            if not isinstance(receipt, dict) or receipt.get("layer") != layer:
                findings.append(f"{skill_rel}: missing {layer} receipt ownership")
    return findings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="docs/governance/skill-policy.json")
    parser.add_argument("--lock", default=".harness.lock")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).resolve()
    try:
        policy = load_object(root / safe_relative(args.policy, "--policy"), "skill policy")
        lock = load_object(root / safe_relative(args.lock, "--lock"), "lock")
        findings = run(root, policy, lock)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"SKILL-G CONFIG: {exc}; copy "
            "docs/governance/skill-policy.example.json and edit it",
            file=sys.stderr,
        )
        return 2
    for finding in findings:
        print(f"SKILL-G {finding}")
    print(f"SKILL-G {len(findings)} finding(s)")
    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
