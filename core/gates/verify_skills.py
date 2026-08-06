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


def skill_roots(policy: dict[str, object]) -> list[Path]:
    """Accept one root or many: a release may fan out into several tool roots."""
    raw = policy.get("skills_root")
    values = raw if isinstance(raw, list) else [raw]
    if not values:
        raise ValueError("skills_root must name at least one directory")
    roots = [safe_relative(item, "skills_root") for item in values]
    if len({item.as_posix() for item in roots}) != len(roots):
        raise ValueError("skills_root contains duplicates")
    return roots


def receipt_skills(roots: list[Path], files: dict[str, object]) -> dict[str, str]:
    """Skills the receipt already owns, with the layer it recorded.

    The lock knows which skills were installed and at which layer, so a policy
    that restated them would be a second copy of the same fact — and the first
    thing to rot when a profile selection changes.
    """
    owned: dict[str, str] = {}
    prefixes = [f"{item.as_posix()}/" for item in roots]
    for path, meta in files.items():
        if not isinstance(meta, dict) or not path.endswith("/SKILL.md"):
            continue
        for prefix in prefixes:
            if path.startswith(prefix):
                name = path[len(prefix):].split("/", 1)[0]
                layer = meta.get("layer")
                if isinstance(layer, str):
                    owned[name] = layer
                break
    return owned


def run(root: Path, policy: dict[str, object], lock: dict[str, object]) -> list[str]:
    roots = skill_roots(policy)
    configured = policy.get("skills", {})
    if not isinstance(configured, dict) or not all(
        isinstance(name, str) and layer in {"core", "profile", "local"}
        for name, layer in configured.items()
    ):
        raise ValueError("skills must map names to core, profile or local")
    files = lock.get("files")
    overrides = lock.get("overrides")
    if not isinstance(files, dict) or not isinstance(overrides, list):
        raise ValueError("lock must contain files and overrides")

    findings: list[str] = []
    # Receipt-owned skills come from the lock; the policy adds local ones and
    # may still name a receipt-owned skill, which must then agree with it.
    owned = receipt_skills(roots, files)
    for name, layer in sorted(configured.items()):
        if name in owned and owned[name] != layer:
            findings.append(
                f"{name}: policy says {layer}, receipt says {owned[name]}"
            )
    configured = {**owned, **configured}
    expected = set(configured)
    present = 0
    for skills_root in roots:
        actual_root = root / skills_root
        # A configured root that was never installed is not a finding: a
        # consumer may select a subset of targets. The receipt, not this gate,
        # proves an install is complete.
        if not actual_root.is_dir():
            continue
        present += 1
        label = skills_root.as_posix()
        actual = {path.name for path in actual_root.iterdir() if path.is_dir()}
        findings.extend(
            f"{label}: unexpected installed skill: {name}"
            for name in sorted(actual - expected)
        )
        findings.extend(
            f"{label}: missing installed skill: {name}"
            for name in sorted(expected - actual)
        )
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
                    findings.append(
                        f"{skill_rel}: local skill is not covered by a lock override"
                    )
                if skill_rel in files:
                    findings.append(f"{skill_rel}: local skill must not be receipt-owned")
            else:
                receipt = files.get(skill_rel)
                if not isinstance(receipt, dict) or receipt.get("layer") != layer:
                    findings.append(f"{skill_rel}: missing {layer} receipt ownership")
    if not present:
        findings.append(
            "no configured skills_root exists: "
            + ", ".join(item.as_posix() for item in roots)
        )
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
