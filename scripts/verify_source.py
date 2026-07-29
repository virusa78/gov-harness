#!/usr/bin/env python3
"""Fail closed on source ownership, portability, and skill-boundary drift."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SKILLS = {
    "adr",
    "karpathy",
    "python-testing-gate",
    "sdd-workflow",
    "shell-testing-gate",
    "truth-pipeline",
}
PROFILE_SKILLS = {"backend-code-review-csharp", "csharp-backend-build-gate"}
RULES = {
    "bdd-format.md",
    "design-discovery-full.md",
    "design-discovery-light.md",
    "design-principles.md",
    "design-review-gate.md",
    "design-review.md",
    "design-synthesis.md",
    "ears-format.md",
    "gap-analysis.md",
    "io-resilience.md",
    "requirements-review-gate.md",
    "steering-principles.md",
    "tasks-generation.md",
    "tasks-parallel-analysis.md",
}
FORBIDDEN = (
    "/home/",
    "superfront2back",
    "DataGridShell",
    "TriagePanel",
    "requirements/CRUD-e2e",
)


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^name:\s*([a-z0-9-]+)\s*$", text, flags=re.MULTILINE)
    if not text.startswith("---\n") or not match or "description:" not in text[:1000]:
        fail(f"invalid skill frontmatter: {path.relative_to(ROOT)}")
    return match.group(1)


def main() -> int:
    core = {path.name for path in (ROOT / "core/skills").iterdir() if path.is_dir()}
    profile_root = ROOT / "profiles/csharp-fintech/skills"
    profile = {path.name for path in profile_root.iterdir() if path.is_dir()}
    rules = {path.name for path in (ROOT / "core/rules").glob("*.md")}
    if core != CORE_SKILLS:
        fail(f"core skill boundary differs: {sorted(core)}")
    if profile != PROFILE_SKILLS:
        fail(f"profile skill boundary differs: {sorted(profile)}")
    if rules != RULES:
        fail(f"rule inventory differs: {sorted(rules)}")
    for directory, expected in (
        (ROOT / "core/skills", CORE_SKILLS),
        (profile_root, PROFILE_SKILLS),
    ):
        for name in expected:
            declared = skill_name(directory / name / "SKILL.md")
            if declared != name:
                fail(f"skill directory/name mismatch: {name} != {declared}")
    for root in (ROOT / "core", ROOT / "profiles"):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in FORBIDDEN:
                if marker.lower() in text.lower():
                    fail(f"project coupling {marker!r} in {path.relative_to(ROOT)}")
    manifest = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))
    destinations = [item["destination"] for item in manifest["files"]]
    if len(destinations) != len(set(destinations)):
        fail("release manifest has duplicate destinations")
    forbidden_roots = (
        "requirements/",
        "contracts/",
        "domain/",
        "docs/architecture/decisions/",
        "docs/LESSONS",
        "docs/intake/",
    )
    if any(str(path).startswith(forbidden_roots) for path in destinations):
        fail("release manifest crosses into project truth")
    if any("latest" in str(value).lower() for value in manifest.values()):
        fail("release manifest may not use latest")
    print(
        f"source boundary clean: {len(rules)} rules, "
        f"{len(core)} core skills, {len(profile)} profile skills"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

