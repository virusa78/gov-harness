#!/usr/bin/env python3
"""Generate the release source map deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release/manifest.json"

# Every profile must be described here: the stack menu (`harness.py select`)
# renders exactly these lines. A discovered profile without a description or a
# description without a profile directory fails the build.
PROFILE_INFO = {
    "adr": "ADR workflow and the ADR-G gate — requires docs/architecture/decisions/",
    "lang/csharp-fintech": "C# financial-backend skills",
    "spec/kiro": "Specification home — .kiro/specs/, reviewer-verified only",
    "spec/openspec": "Specification home — OpenSpec (needs the global CLI)",
    "spec/plain": "Specification home — plain requirements/, no tool behind it",
    "testing/python-tools": "Python verification-script discipline (dev tooling)",
    "transport/kafka": "Kafka/Redpanda messaging — offset, outbox and DLQ discipline",
    "transport/nats": "NATS/JetStream messaging — ack, redelivery and DLQ discipline",
}

# Subtrees the harness owns outright in a consumer project: anything inside
# them that the current receipt does not own is pruned on init --reinstall/sync.
MANAGED_ROOTS = [".agents/skills"]

# Content kinds a profile directory may carry. A directory holding none of
# them is a family, and its children are its variants.
SUBTREES = ("skills", "rules", "gates")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def discover_profiles() -> dict[str, Path]:
    """Map profile name -> profile directory.

    A profile directory is one that contains skills/ or rules/. Directories
    directly under profiles/ are standalone profiles; one level deeper they
    are family/variant profiles. Anything else is an error.
    """
    profiles: dict[str, Path] = {}
    for first in sorted((ROOT / "profiles").iterdir()):
        if not first.is_dir():
            raise RuntimeError(f"unexpected file under profiles/: {first.name}")
        if any((first / kind).is_dir() for kind in SUBTREES):
            profiles[first.name] = first
            continue
        variants = sorted(path for path in first.iterdir() if path.is_dir())
        if not variants:
            raise RuntimeError(f"empty profile family: profiles/{first.name}")
        for variant in variants:
            if not any((variant / kind).is_dir() for kind in SUBTREES):
                raise RuntimeError(
                    f"profile variant lacks {'/, '.join(SUBTREES)}/: "
                    f"profiles/{first.name}/{variant.name}"
                )
            profiles[f"{first.name}/{variant.name}"] = variant
    return profiles


def entries() -> list[dict[str, object]]:
    mappings: list[tuple[Path, str, str, str | None, bool]] = [
        (ROOT / "harness.py", "scripts/harness.py", "core", None, False),
        (
            ROOT / "core/gates/governance_docs.py",
            "scripts/governance_docs.py",
            "core",
            None,
            False,
        ),
        (
            ROOT / "core/gates/verify-docs.sh",
            "scripts/verify-docs.sh",
            "core",
            None,
            False,
        ),
        (
            ROOT / "core/gates/sync_agent_stubs.py",
            "scripts/sync-agent-stubs.py",
            "core",
            None,
            False,
        ),
        (
            ROOT / "core/gates/verify_skills.py",
            "scripts/verify-skills.py",
            "core",
            None,
            False,
        ),
    ]
    for path in sorted((ROOT / "core/policies").glob("*.example.json")):
        mappings.append(
            (path, f"docs/governance/{path.name}", "core", None, False)
        )
    for path in sorted((ROOT / "core/rules").glob("*.md")):
        mappings.append(
            (
                path,
                f"docs/governance/rules/{path.name}",
                "core",
                None,
                path.name == "ears-format.md",
            )
        )
    for path in sorted((ROOT / "core/skills").glob("**/*")):
        if path.is_file():
            rel = path.relative_to(ROOT / "core/skills").as_posix()
            mappings.append(
                (path, f".agents/skills/{rel}", "core", None, False)
            )
    profiles = discover_profiles()
    if set(profiles) != set(PROFILE_INFO):
        missing = sorted(set(profiles) - set(PROFILE_INFO))
        stale = sorted(set(PROFILE_INFO) - set(profiles))
        raise RuntimeError(
            f"PROFILE_INFO out of date: undescribed={missing} described-but-absent={stale}"
        )
    for name, base in sorted(profiles.items()):
        skills_root = base / "skills"
        if skills_root.is_dir():
            for path in sorted(skills_root.glob("**/*")):
                if path.is_file():
                    rel = path.relative_to(skills_root).as_posix()
                    mappings.append(
                        (path, f".agents/skills/{rel}", "profile", name, False)
                    )
        rules_root = base / "rules"
        if rules_root.is_dir():
            for path in sorted(rules_root.glob("*.md")):
                mappings.append(
                    (
                        path,
                        f"docs/governance/rules/{path.name}",
                        "profile",
                        name,
                        False,
                    )
                )
        gates_root = base / "gates"
        if gates_root.is_dir():
            for path in sorted(gates_root.glob("*.py")):
                script = path.stem.replace("_", "-") + path.suffix
                mappings.append(
                    (path, f"scripts/{script}", "profile", name, False)
                )
    result = []
    for source, destination, layer, profile, templated in mappings:
        if not source.is_file():
            raise RuntimeError(f"missing release source: {source}")
        result.append(
            {
                "source": source.relative_to(ROOT).as_posix(),
                "destination": destination,
                "layer": layer,
                "profile": profile,
                "templated": templated,
                "executable": source.suffix in {".py", ".sh"},
                "sha256": digest(source),
            }
        )
    return sorted(
        result, key=lambda item: (str(item["destination"]), str(item["profile"]))
    )


def manifest(version: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "version": version,
        "required_params": ["golden_sample"],
        "managed_roots": list(MANAGED_ROOTS),
        "profile_info": [
            {"name": name, "description": PROFILE_INFO[name]}
            for name in sorted(PROFILE_INFO)
        ],
        "files": entries(),
    }


def encoded(value: dict[str, object]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = encoded(manifest(args.version))
    if args.check:
        actual = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if actual != expected:
            print("release/manifest.json is stale", file=sys.stderr)
            return 1
        print("release manifest reproducible")
        return 0
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(expected, encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
