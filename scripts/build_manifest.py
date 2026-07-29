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


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


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
    profile_root = ROOT / "profiles/csharp-fintech/skills"
    for path in sorted(profile_root.glob("**/*")):
        if path.is_file():
            rel = path.relative_to(profile_root).as_posix()
            mappings.append(
                (
                    path,
                    f".agents/skills/{rel}",
                    "profile",
                    "csharp-fintech",
                    False,
                )
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
                "sha256": digest(source),
            }
        )
    return sorted(result, key=lambda item: str(item["destination"]))


def manifest(version: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "version": version,
        "required_params": ["golden_sample"],
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
