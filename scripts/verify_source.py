#!/usr/bin/env python3
"""Fail closed on source ownership, portability, and skill-boundary drift."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SKILLS = {
    "karpathy",
    "sdd-workflow",
    "shell-testing-gate",
    "truth-pipeline",
}
# profile name -> (skill directory names, rule file names)
PROFILES: dict[str, tuple[set[str], set[str]]] = {
    "adr": ({"adr"}, set()),
    "lang/csharp-fintech": (
        {"backend-code-review-csharp", "csharp-backend-build-gate"},
        set(),
    ),
    "testing/python-tools": ({"python-testing-gate"}, set()),
    "transport/kafka": (set(), {"io-resilience.md"}),
    "transport/nats": (set(), {"io-resilience.md"}),
}
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


def check_rule_metadata(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required = (
        "---\n",
        "id: governance/rules/",
        "class: state",
        "status: active",
        "owner: governance-harness",
        "updated:",
        "sources:",
    )
    if not all(marker in text[:500] for marker in required):
        fail(f"rule lifecycle metadata is incomplete: {path.relative_to(ROOT)}")


def profile_family(name: str | None) -> str | None:
    if name and "/" in name:
        return name.split("/", 1)[0]
    return None


def main() -> int:
    core = {path.name for path in (ROOT / "core/skills").iterdir() if path.is_dir()}
    rules = {path.name for path in (ROOT / "core/rules").glob("*.md")}
    if core != CORE_SKILLS:
        fail(f"core skill boundary differs: {sorted(core)}")
    if rules != RULES:
        fail(f"rule inventory differs: {sorted(rules)}")
    for path in (ROOT / "core/rules").glob("*.md"):
        check_rule_metadata(path)
    for name in CORE_SKILLS:
        declared = skill_name(ROOT / "core/skills" / name / "SKILL.md")
        if declared != name:
            fail(f"skill directory/name mismatch: {name} != {declared}")

    for profile, (skills, rule_files) in PROFILES.items():
        base = ROOT / "profiles" / profile
        actual_skills = (
            {path.name for path in (base / "skills").iterdir() if path.is_dir()}
            if (base / "skills").is_dir()
            else set()
        )
        actual_rules = (
            {path.name for path in (base / "rules").glob("*.md")}
            if (base / "rules").is_dir()
            else set()
        )
        if actual_skills != skills:
            fail(f"profile {profile} skill boundary differs: {sorted(actual_skills)}")
        if actual_rules != rule_files:
            fail(f"profile {profile} rule boundary differs: {sorted(actual_rules)}")
        for name in skills:
            declared = skill_name(base / "skills" / name / "SKILL.md")
            if declared != name:
                fail(f"skill directory/name mismatch: {name} != {declared}")
        for name in rule_files:
            check_rule_metadata(base / "rules" / name)
    known_profile_dirs = set()
    for profile in PROFILES:
        known_profile_dirs.add((ROOT / "profiles" / profile).resolve())
    for first in (ROOT / "profiles").iterdir():
        if not first.is_dir():
            fail(f"unexpected file under profiles/: {first.name}")
        if first.resolve() in known_profile_dirs:
            continue
        for variant in first.iterdir():
            if variant.resolve() not in known_profile_dirs:
                fail(f"undeclared profile directory: {variant.relative_to(ROOT)}")

    for root in (ROOT / "core", ROOT / "profiles"):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in FORBIDDEN:
                if marker.lower() in text.lower():
                    fail(f"project coupling {marker!r} in {path.relative_to(ROOT)}")

    manifest = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))
    owners: dict[str, tuple[str, str | None]] = {}
    for item in manifest["files"]:
        destination = str(item["destination"])
        layer = str(item["layer"])
        profile = item.get("profile")
        existing = owners.get(destination)
        if existing is None:
            owners[destination] = (layer, profile)
            continue
        existing_layer, existing_profile = existing
        same_family_variants = (
            existing_layer == "profile"
            and layer == "profile"
            and existing_profile != profile
            and profile_family(str(existing_profile)) is not None
            and profile_family(str(existing_profile)) == profile_family(str(profile))
        )
        if not same_family_variants:
            fail(f"release manifest has duplicate destination: {destination}")
    forbidden_roots = (
        "requirements/",
        "contracts/",
        "domain/",
        "docs/architecture/decisions/",
        "docs/LESSONS",
        "docs/intake/",
    )
    if any(str(path).startswith(forbidden_roots) for path in owners):
        fail("release manifest crosses into project truth")
    if any("latest" in str(value).lower() for value in manifest.values()):
        fail("release manifest may not use latest")
    profile_count = sum(len(skills) for skills, _ in PROFILES.values())
    rule_variants = sum(len(rule_files) for _, rule_files in PROFILES.values())
    print(
        f"source boundary clean: {len(rules)} core rules, "
        f"{len(core)} core skills, {profile_count} profile skills, "
        f"{rule_variants} profile rule variants"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
