#!/usr/bin/env python3
"""POLICY-G exists because a project-owned file cannot be updated by the harness.

The pilot proved the failure mode: `stub-policy.json` predated `agents_file`,
and `docs-policy.json` predated the three evidence keys. Every gate reported
clean, EVID-G printed a cheerful SKIP, and nothing told the project that four
capabilities had shipped and were sitting unused.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "core/gates/verify_policies.py"
sys.path.insert(0, str(ROOT / "core/gates"))
import verify_policies as vp  # noqa: E402


class ComparisonTests(unittest.TestCase):
    def test_a_copy_matching_its_example_is_clean(self) -> None:
        example = {"schema_version": 1, "a": 1, "b": 2}
        copy = {"schema_version": 1, "a": 9, "b": 8}
        self.assertEqual([], vp.compare(example, copy, "x.json"))

    def test_commentary_keys_are_not_compared(self) -> None:
        example = {"schema_version": 1, "_about": ["docs"], "a": 1}
        copy = {"schema_version": 1, "a": 1}
        self.assertEqual([], vp.compare(example, copy, "x.json"))

    def test_a_key_the_release_added_is_a_finding(self) -> None:
        example = {"schema_version": 1, "a": 1, "agents_file": "AGENTS.md"}
        copy = {"schema_version": 1, "a": 1}
        findings = vp.compare(example, copy, "stub-policy.json")
        self.assertEqual(1, len(findings), findings)
        self.assertIn("agents_file", findings[0])

    def test_declining_a_key_silences_it(self) -> None:
        """Declining is a decision and leaves a trace; not knowing is neither."""
        example = {"schema_version": 1, "a": 1, "agents_file": "AGENTS.md"}
        copy = {"schema_version": 1, "a": 1, "_declined": ["agents_file"]}
        self.assertEqual([], vp.compare(example, copy, "stub-policy.json"))

    def test_a_key_the_example_does_not_define_is_a_finding(self) -> None:
        example = {"schema_version": 1, "a": 1}
        copy = {"schema_version": 1, "a": 1, "agents_fil": "AGENTS.md"}
        findings = vp.compare(example, copy, "stub-policy.json")
        self.assertTrue(any("agents_fil" in f for f in findings), findings)

    def test_declining_something_configured_is_a_contradiction(self) -> None:
        example = {"schema_version": 1, "agents_file": "AGENTS.md"}
        copy = {"schema_version": 1, "agents_file": "A.md", "_declined": ["agents_file"]}
        findings = vp.compare(example, copy, "stub-policy.json")
        self.assertTrue(any("disagree" in f for f in findings), findings)

    def test_a_stale_declination_is_a_finding(self) -> None:
        """Otherwise _declined accumulates names of things that no longer exist."""
        example = {"schema_version": 1, "a": 1}
        copy = {"schema_version": 1, "a": 1, "_declined": ["removed_key"]}
        findings = vp.compare(example, copy, "stub-policy.json")
        self.assertTrue(any("no longer" in f for f in findings), findings)

    def test_a_schema_version_gap_is_a_finding(self) -> None:
        example = {"schema_version": 2, "a": 1}
        copy = {"schema_version": 1, "a": 1}
        findings = vp.compare(example, copy, "stub-policy.json")
        self.assertTrue(any("schema_version" in f for f in findings), findings)

    def test_a_malformed_declined_list_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            vp.compare({"a": 1}, {"a": 1, "_declined": "agents_file"}, "x.json")


class EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.governance = self.root / "docs/governance"
        self.governance.mkdir(parents=True)
        self.addCleanup(self.tmp.cleanup)

    def write(self, name: str, document: dict) -> None:
        (self.governance / name).write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )

    def run_gate(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATE), "--root", str(self.root), *args],
            check=False, capture_output=True, text=True,
        )

    def test_no_governance_directory_skips(self) -> None:
        done = subprocess.run(
            [sys.executable, str(GATE), "--root", str(self.root / "nowhere")],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(0, done.returncode)
        self.assertIn("SKIP POLICY-G", done.stderr)

    def test_an_example_without_a_copy_is_not_a_finding(self) -> None:
        """Not adopting a gate is a legitimate state."""
        self.write("stub-policy.example.json", {"schema_version": 1, "agents_file": "A"})
        done = self.run_gate()
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertIn("0 finding(s)", done.stdout)

    def test_a_copy_behind_its_example_fails(self) -> None:
        self.write("stub-policy.example.json", {"schema_version": 1, "agents_file": "A"})
        self.write("stub-policy.json", {"schema_version": 1})
        done = self.run_gate()
        self.assertEqual(2, done.returncode)
        self.assertIn("agents_file", done.stdout)

    def test_declining_makes_it_pass(self) -> None:
        self.write("stub-policy.example.json", {"schema_version": 1, "agents_file": "A"})
        self.write("stub-policy.json", {"schema_version": 1, "_declined": ["agents_file"]})
        done = self.run_gate()
        self.assertEqual(0, done.returncode, done.stdout)

    def test_malformed_json_is_a_config_error_not_a_pass(self) -> None:
        self.write("stub-policy.example.json", {"schema_version": 1})
        (self.governance / "stub-policy.json").write_text("{not json", encoding="utf-8")
        done = self.run_gate()
        self.assertEqual(3, done.returncode)
        self.assertIn("POLICY-G CONFIG", done.stderr)

    def test_a_path_outside_the_root_is_refused(self) -> None:
        done = self.run_gate("--policies", "../elsewhere")
        self.assertEqual(3, done.returncode)


class ShippedExamplesTests(unittest.TestCase):
    def test_every_example_documents_how_to_decline(self) -> None:
        """The gate demands something; the file the consumer reads must say so."""
        for path in sorted((ROOT / "core/policies").glob("*.example.json")):
            with self.subTest(policy=path.name):
                about = " ".join(json.loads(path.read_text(encoding="utf-8"))["_about"])
                self.assertIn("_declined", about)
                self.assertIn("POLICY-G", about)

    def test_this_repository_ships_the_gate(self) -> None:
        manifest = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))
        destinations = {entry["destination"] for entry in manifest["files"]}
        self.assertIn("scripts/verify-policies.py", destinations)


if __name__ == "__main__":
    unittest.main()
