#!/usr/bin/env python3
"""Three defects found by installing v0.6.0-rc.1 over a live v0.1.0-rc.8 pilot.

None was visible to the unit suite or the source verifier: each needs a real
project with a real prior install. Lesson L4, applied.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness.py"
SKILLS_GATE = ROOT / "core/gates/verify_skills.py"
VERSION = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))["version"]


def install(project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS), "init", "--project", str(project),
         "--source", "virusa78/gov-harness", "--to", VERSION,
         "--from-dir", str(ROOT), "--param", "golden_sample=README.md", *extra],
        check=False, capture_output=True, text=True,
    )


class RenameHintTests(unittest.TestCase):
    """A profile that moved into a family keeps its variant name."""

    def test_the_refusal_names_the_new_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            done = install(project, "--profile", "csharp-fintech")
            self.assertEqual(3, done.returncode)
            output = done.stdout + done.stderr
            self.assertIn("unknown profile(s): csharp-fintech", output)
            self.assertIn("renamed: csharp-fintech -> lang/csharp-fintech", output)

    def test_a_genuinely_unknown_profile_gets_no_hint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            done = install(project, "--profile", "nonsense")
            self.assertEqual(3, done.returncode)
            self.assertNotIn("renamed:", done.stdout + done.stderr)


class PrerequisiteTests(unittest.TestCase):
    """A profile declaring a path prerequisite is checked before installing."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.project = Path(self._temp.name) / "project"
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)

    def test_a_missing_prerequisite_refuses_the_install(self) -> None:
        done = install(self.project, "--profile", "adr")
        self.assertEqual(3, done.returncode)
        self.assertIn(
            "profile prerequisite is missing: adr requires docs/architecture/decisions",
            done.stdout + done.stderr,
        )
        self.assertFalse((self.project / ".harness.lock").exists(), "installed anyway")

    def test_a_satisfied_prerequisite_installs(self) -> None:
        (self.project / "docs/architecture/decisions").mkdir(parents=True)
        done = install(self.project, "--profile", "adr")
        self.assertEqual(0, done.returncode, done.stderr)

    def test_a_profile_without_a_prerequisite_is_unaffected(self) -> None:
        done = install(self.project, "--profile", "spec/plain")
        self.assertEqual(0, done.returncode, done.stderr)


class SkillPolicyFromLockTests(unittest.TestCase):
    """SKILL-G reads receipt-owned skills from the lock, not from the policy."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.project = Path(self._temp.name) / "project"
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        done = install(
            self.project, "--profile", "spec/plain", "--profile", "workflow/superpowers"
        )
        self.assertEqual(0, done.returncode, done.stderr)
        governance = self.project / "docs/governance"
        (governance / "skill-policy.json").write_text(
            (governance / "skill-policy.example.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def gate(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SKILLS_GATE), "--root", str(self.project)],
            check=False, capture_output=True, text=True,
        )

    def test_the_unedited_example_is_clean_over_core_and_profile_skills(self) -> None:
        done = self.gate()
        self.assertEqual(0, done.returncode, done.stdout)

    def test_a_hand_copied_skill_is_still_caught(self) -> None:
        stray = self.project / ".claude/skills/handmade"
        stray.mkdir(parents=True)
        (stray / "SKILL.md").write_text(
            "---\nname: handmade\ndescription: x\n---\n", encoding="utf-8"
        )
        done = self.gate()
        self.assertEqual(2, done.returncode)
        self.assertIn("unexpected installed skill: handmade", done.stdout)

    def test_a_policy_contradicting_the_receipt_is_a_finding(self) -> None:
        policy_path = self.project / "docs/governance/skill-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["skills"] = {"sdd-workflow": "local"}
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        done = self.gate()
        self.assertEqual(2, done.returncode)
        self.assertIn("policy says local, receipt says core", done.stdout)


if __name__ == "__main__":
    unittest.main()
