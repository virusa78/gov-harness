#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "core/gates/sync_agent_stubs.py"
SKILLS = ROOT / "core/gates/verify_skills.py"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class GateTests(unittest.TestCase):
    def test_stub_round_trip_and_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs/governance/rules/example.md"
            source.parent.mkdir(parents=True)
            source.write_text("# rule\n", encoding="utf-8")
            write_json(
                root / "policy.json",
                {
                    "schema_version": 1,
                    "rules": ["example.md"],
                    "canonical_root": "docs/governance/rules",
                    "stub_roots": [".kiro/settings/rules"],
                    "forbidden_content_roots": [".agents/skills/sdd-workflow/rules"],
                },
            )
            command = [
                sys.executable,
                str(STUBS),
                "--root",
                str(root),
                "--policy",
                "policy.json",
            ]
            self.assertEqual(0, subprocess.run(command + ["--write"]).returncode)
            self.assertEqual(0, subprocess.run(command).returncode)
            (root / ".kiro/settings/rules/example.md").write_text(
                "# fork\n", encoding="utf-8"
            )
            self.assertEqual(2, subprocess.run(command).returncode)

    def test_skill_receipt_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("core-skill", "local-skill"):
                path = root / ".agents/skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True)
                path.write_text(
                    f"---\nname: {name}\ndescription: Trigger {name}.\n---\n",
                    encoding="utf-8",
                )
            write_json(
                root / "policy.json",
                {
                    "schema_version": 1,
                    "skills_root": ".agents/skills",
                    "skills": {"core-skill": "core", "local-skill": "local"},
                },
            )
            write_json(
                root / ".harness.lock",
                {
                    "schema_version": 1,
                    "files": {
                        ".agents/skills/core-skill/SKILL.md": {"layer": "core"}
                    },
                    "overrides": [".agents/skills/local-skill/**"],
                },
            )
            command = [
                sys.executable,
                str(SKILLS),
                "--root",
                str(root),
                "--policy",
                "policy.json",
            ]
            self.assertEqual(0, subprocess.run(command).returncode)
            extra = root / ".agents/skills/extra/SKILL.md"
            extra.parent.mkdir(parents=True)
            extra.write_text(
                "---\nname: extra\ndescription: extra\n---\n", encoding="utf-8"
            )
            self.assertEqual(2, subprocess.run(command).returncode)


if __name__ == "__main__":
    unittest.main()
