#!/usr/bin/env python3
"""The generated AGENTS.md doctrine block (ADR-0013)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "core/gates/sync_agent_stubs.py"
sys.path.insert(0, str(GATE.parent))
import sync_agent_stubs as stubs  # noqa: E402

PROJECT_TEXT = "# Our project\n\nOur own rules that must survive.\n\n## Build\n\nmake all\n"


class SpliceTests(unittest.TestCase):
    """Pure text surgery: everything outside the markers is untouched."""

    BLOCK = f"{stubs.BEGIN}\nbody\n{stubs.END}\n"

    def test_an_empty_file_becomes_the_block(self) -> None:
        self.assertEqual(self.BLOCK, stubs.splice("", self.BLOCK))

    def test_an_existing_file_keeps_its_content(self) -> None:
        spliced = stubs.splice(PROJECT_TEXT, self.BLOCK)
        self.assertTrue(spliced.startswith(PROJECT_TEXT))
        self.assertIn(stubs.BEGIN, spliced)

    def test_replacing_a_block_preserves_both_sides(self) -> None:
        original = stubs.splice(PROJECT_TEXT, self.BLOCK) + "\ntrailing note\n"
        replaced = stubs.splice(original, f"{stubs.BEGIN}\nnew body\n{stubs.END}\n")
        self.assertIn("Our own rules that must survive", replaced)
        self.assertIn("trailing note", replaced)
        self.assertIn("new body", replaced)
        self.assertNotIn("\nbody\n", replaced)

    def test_splicing_is_idempotent(self) -> None:
        once = stubs.splice(PROJECT_TEXT, self.BLOCK)
        self.assertEqual(once, stubs.splice(once, self.BLOCK))

    def test_an_unterminated_marker_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            stubs.splice(f"text\n{stubs.BEGIN}\nno end marker\n", self.BLOCK)


class BlockContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        self.rules = self.root / "docs/governance/rules"
        self.rules.mkdir(parents=True)
        for name in ("ears-format", "spec-home", "bdd-format"):
            (self.rules / f"{name}.md").write_text("# rule\n", encoding="utf-8")

    def block(self) -> str:
        return stubs.agents_block(self.root, Path("docs/governance/rules"))

    def test_it_lists_the_installed_rules(self) -> None:
        block = self.block()
        for name in ("ears-format", "spec-home", "bdd-format"):
            self.assertIn(f"`{name}`", block)

    def test_it_points_at_the_canonical_home_without_restating_doctrine(self) -> None:
        """A second copy of the rules here would be the first one to rot."""
        block = self.block()
        self.assertIn("docs/governance/rules/", block)
        self.assertIn("holds no doctrine of its own", block)

    def test_the_single_spec_home_invariant_appears_when_bound(self) -> None:
        self.assertIn("exactly one home", self.block())

    def test_it_is_silent_about_the_spec_home_when_unbound(self) -> None:
        (self.rules / "spec-home.md").unlink()
        self.assertNotIn("exactly one home", self.block())


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        (self.root / "docs/governance/rules").mkdir(parents=True)
        (self.root / "docs/governance/rules/ears-format.md").write_text(
            "# rule\n", encoding="utf-8"
        )
        (self.root / "policy.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "agents_file": "AGENTS.md",
                    "canonical_root": "docs/governance/rules",
                    "rules": [],
                    "stub_roots": [],
                    "forbidden_content_roots": [],
                }
            ),
            encoding="utf-8",
        )
        self.agents = self.root / "AGENTS.md"

    def gate(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GATE), "--root", str(self.root),
             "--policy", "policy.json", *extra],
            check=False, capture_output=True, text=True,
        )

    def test_a_missing_block_is_a_finding(self) -> None:
        done = self.gate()
        self.assertEqual(2, done.returncode)
        self.assertIn("missing generated doctrine block", done.stdout)

    def test_write_creates_it_and_the_gate_then_passes(self) -> None:
        self.assertEqual(0, self.gate("--write").returncode)
        self.assertEqual(0, self.gate().returncode)

    def test_an_edit_inside_the_block_is_stale(self) -> None:
        self.gate("--write")
        self.agents.write_text(
            self.agents.read_text(encoding="utf-8").replace(
                "holds no doctrine", "holds plenty of doctrine"
            ),
            encoding="utf-8",
        )
        done = self.gate()
        self.assertEqual(2, done.returncode)
        self.assertIn("stale generated doctrine block", done.stdout)

    def test_an_edit_outside_the_block_is_left_alone(self) -> None:
        self.gate("--write")
        self.agents.write_text(
            PROJECT_TEXT + self.agents.read_text(encoding="utf-8"), encoding="utf-8"
        )
        self.assertEqual(0, self.gate().returncode)

    def test_omitting_the_key_opts_out_entirely(self) -> None:
        policy = json.loads((self.root / "policy.json").read_text(encoding="utf-8"))
        del policy["agents_file"]
        (self.root / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
        self.assertEqual(0, self.gate().returncode)
        self.assertFalse(self.agents.exists())


if __name__ == "__main__":
    unittest.main()
