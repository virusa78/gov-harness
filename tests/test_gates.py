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

    def test_skill_boundary_across_fanned_out_roots(self) -> None:
        """A release fans one skill into several tool roots; all are checked."""
        roots = [".agents/skills", ".claude/skills", ".codex/skills"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = {}
            # Only two of the three roots are installed: selecting a subset of
            # targets must stay quiet, not report the absent root.
            for skills_root in roots[:2]:
                path = root / skills_root / "core-skill/SKILL.md"
                path.parent.mkdir(parents=True)
                path.write_text(
                    "---\nname: core-skill\ndescription: Trigger it.\n---\n",
                    encoding="utf-8",
                )
                receipts[f"{skills_root}/core-skill/SKILL.md"] = {"layer": "core"}
            write_json(
                root / "policy.json",
                {
                    "schema_version": 1,
                    "skills_root": roots,
                    "skills": {"core-skill": "core"},
                },
            )
            write_json(
                root / ".harness.lock",
                {"schema_version": 1, "files": receipts, "overrides": []},
            )
            command = [
                sys.executable, str(SKILLS), "--root", str(root),
                "--policy", "policy.json",
            ]
            self.assertEqual(0, subprocess.run(command).returncode)

            # A hand-copied skill in a non-primary root is the failure this
            # gate exists for.
            stray = root / ".claude/skills/handmade/SKILL.md"
            stray.parent.mkdir(parents=True)
            stray.write_text("---\nname: handmade\ndescription: x\n---\n", encoding="utf-8")
            done = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(2, done.returncode)
            self.assertIn(".claude/skills: unexpected installed skill: handmade", done.stdout)

    def test_no_installed_skill_root_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(
                root / "policy.json",
                {
                    "schema_version": 1,
                    "skills_root": [".agents/skills"],
                    "skills": {},
                },
            )
            write_json(
                root / ".harness.lock",
                {"schema_version": 1, "files": {}, "overrides": []},
            )
            done = subprocess.run(
                [sys.executable, str(SKILLS), "--root", str(root),
                 "--policy", "policy.json"],
                capture_output=True, text=True,
            )
            self.assertEqual(2, done.returncode)
            self.assertIn("no configured skills_root exists", done.stdout)


if __name__ == "__main__":
    unittest.main()
