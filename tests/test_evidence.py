#!/usr/bin/env python3
"""EVID-G — a completion claim must be a record, not a sentence (ADR-0014)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "core/gates/verify_evidence.py"
PATTERN = r"^###\s+Requirement:\s*(.+?)\s*$"
REQUIREMENTS = (
    "# Billing\n\n"
    "### Requirement: LOT-U1\nThe system shall refund a captured payment.\n\n"
    "### Requirement: LOT-U2\nThe system shall reject an excessive refund.\n"
)


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True)
        (self.root / "requirements").mkdir()
        (self.root / "requirements/billing.md").write_text(REQUIREMENTS, encoding="utf-8")
        (self.root / "docs/governance").mkdir(parents=True)
        (self.root / "docs/governance/docs-policy.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "requirements_source": "requirements",
                    "requirement_pattern": PATTERN,
                    "evidence_journal": ".evidence.jsonl",
                }
            ),
            encoding="utf-8",
        )
        self.commit("init")

    def commit(self, message: str) -> str:
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", message],
            check=True, capture_output=True,
        )
        return subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    def gate(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GATE), "--root", str(self.root), *args],
            check=False, capture_output=True, text=True,
        )

    def record(self, requirement: str, code: int = 0) -> subprocess.CompletedProcess[str]:
        return self.gate(
            "record", "--requirement", requirement, "--",
            sys.executable, "-c", f"raise SystemExit({code})",
        )

    def test_a_requirement_without_evidence_is_refused(self) -> None:
        done = self.gate("verify")
        self.assertEqual(2, done.returncode)
        self.assertIn("LOT-U1 (requirements/billing.md): no evidence recorded", done.stdout)

    def test_recording_captures_the_real_exit_code(self) -> None:
        self.record("LOT-U1", code=7)
        entry = json.loads((self.root / ".evidence.jsonl").read_text(encoding="utf-8").strip())
        self.assertEqual(7, entry["exit"])
        self.assertEqual("LOT-U1", entry["requirement"])
        self.assertTrue(str(entry["output_sha256"]).startswith("sha256:"))

    def test_a_failing_record_is_not_evidence(self) -> None:
        self.record("LOT-U1", code=0)
        self.record("LOT-U2", code=1)
        done = self.gate("verify")
        self.assertEqual(2, done.returncode)
        self.assertIn("LOT-U2: every fresh record failed", done.stdout)

    def test_fresh_passing_evidence_for_every_requirement_passes(self) -> None:
        self.record("LOT-U1")
        self.record("LOT-U2")
        done = self.gate("verify")
        self.assertEqual(0, done.returncode, done.stdout)

    def test_evidence_goes_stale_when_the_code_changes(self) -> None:
        """The load-bearing rule: proof from before the change is not proof."""
        self.record("LOT-U1")
        self.record("LOT-U2")
        self.assertEqual(0, self.gate("verify").returncode)
        (self.root / "refund.py").write_text("# new implementation\n", encoding="utf-8")
        self.commit("change the implementation")
        done = self.gate("verify")
        self.assertEqual(2, done.returncode)
        self.assertIn("evidence is stale", done.stdout)

    def test_re_recording_after_a_change_clears_it(self) -> None:
        self.record("LOT-U1")
        self.record("LOT-U2")
        (self.root / "refund.py").write_text("# new\n", encoding="utf-8")
        self.commit("change")
        self.record("LOT-U1")
        self.record("LOT-U2")
        self.assertEqual(0, self.gate("verify").returncode)

    def test_replay_catches_a_fabricated_record(self) -> None:
        """A hand-written record is a claim until the command is re-run."""
        self.record("LOT-U1")
        self.record("LOT-U2")
        head = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        with (self.root / ".evidence.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "type": "evidence", "requirement": "LOT-U1",
                "command": [sys.executable, "-c", "raise SystemExit(3)"],
                "exit": 0, "output_sha256": "sha256:fake",
                "commit": head, "at": "2026-08-06T18:00:00Z",
            }, sort_keys=True) + "\n")
        self.assertEqual(0, self.gate("verify").returncode, "cheap pass is expected")
        done = self.gate("verify", "--replay")
        self.assertEqual(2, done.returncode)
        self.assertIn("replay exit 3, record says 0", done.stdout)

    def test_a_corrupt_journal_fails_closed(self) -> None:
        self.record("LOT-U1")
        self.record("LOT-U2")
        with (self.root / ".evidence.jsonl").open("a", encoding="utf-8") as stream:
            stream.write('{"type":"evidence" broken\n')
        done = self.gate("verify")
        self.assertEqual(2, done.returncode)
        self.assertIn("corrupt record; the journal cannot be trusted", done.stdout)

    def test_evidence_for_a_deleted_requirement_is_reported(self) -> None:
        self.record("LOT-U1")
        self.record("LOT-U2")
        (self.root / "requirements/billing.md").write_text(
            "# Billing\n\n### Requirement: LOT-U1\nOnly this one now.\n", encoding="utf-8"
        )
        self.commit("drop a requirement")
        self.record("LOT-U1")
        done = self.gate("verify")
        self.assertEqual(2, done.returncode)
        self.assertIn("LOT-U2: evidence for a requirement that no longer exists", done.stdout)

    def test_the_gate_skips_when_unconfigured(self) -> None:
        (self.root / "docs/governance/docs-policy.json").write_text(
            json.dumps({"schema_version": 1}), encoding="utf-8"
        )
        done = self.gate("verify")
        self.assertEqual(0, done.returncode)
        self.assertIn("SKIP EVID-G", done.stdout)

    def test_recording_outside_a_repository_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as bare:
            done = subprocess.run(
                [sys.executable, str(GATE), "--root", bare, "record",
                 "--requirement", "X", "--", sys.executable, "-c", "pass"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(2, done.returncode)
            self.assertIn("needs a Git repository", done.stderr)


if __name__ == "__main__":
    unittest.main()
