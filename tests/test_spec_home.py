#!/usr/bin/env python3
"""DOC-G6 single specification home and the DOC-G2 absorption record."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "core/gates/governance_docs.py"
HOMES = ["openspec/specs", ".kiro/specs", "requirements"]


def base_policy(**overrides: object) -> dict[str, object]:
    policy: dict[str, object] = {
        "schema_version": 1,
        "link_roots": ["docs"],
        "link_excludes": [],
        "metadata_roots": ["docs"],
        "metadata_excludes": [],
        "legacy_missing_frontmatter_max": 0,
        "seal_roots": ["docs"],
        "portability_roots": ["docs"],
        "portability_excludes": [],
        "environment_owner": "docs/environment.md",
    }
    policy.update(overrides)
    return policy


def document(root: Path, relative: str, *frontmatter: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "".join(f"{line}\n" for line in frontmatter) + "---\n\n# Doc\n",
        encoding="utf-8",
    )
    return path


def run(root: Path, gate: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(root),
            "--config",
            "policy.json",
            "--mode",
            "block",
            "--gate",
            gate,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


class SpecHomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        (self.root / "docs").mkdir()

    def policy(self, **overrides: object) -> None:
        (self.root / "policy.json").write_text(
            json.dumps(base_policy(**overrides)), encoding="utf-8"
        )

    def populate(self, home: str) -> None:
        path = self.root / home / "capability"
        path.mkdir(parents=True)
        (path / "spec.md").write_text("# spec\n", encoding="utf-8")

    def test_unconfigured_homes_skip_the_gate(self) -> None:
        self.policy()
        self.populate("openspec/specs")
        self.populate("requirements")
        result = run(self.root, "DOC-G6")
        self.assertEqual(0, result.returncode)
        self.assertIn("DOC-G6: spec_homes is not configured", result.stdout)

    def test_one_populated_home_passes(self) -> None:
        self.policy(spec_homes=HOMES)
        self.populate("openspec/specs")
        self.assertEqual(0, run(self.root, "DOC-G6").returncode)

    def test_empty_candidate_directory_is_not_a_home(self) -> None:
        self.policy(spec_homes=HOMES)
        self.populate("openspec/specs")
        (self.root / "requirements").mkdir()
        self.assertEqual(0, run(self.root, "DOC-G6").returncode)

    def test_two_populated_homes_without_a_declaration_fail(self) -> None:
        self.policy(spec_homes=HOMES)
        self.populate("openspec/specs")
        self.populate("requirements")
        result = run(self.root, "DOC-G6")
        self.assertEqual(1, result.returncode)
        self.assertIn("several specification homes hold content", result.stdout)

    def test_declared_home_names_the_offender(self) -> None:
        self.policy(spec_homes=HOMES, spec_home="openspec/specs")
        self.populate("openspec/specs")
        self.populate(".kiro/specs")
        result = run(self.root, "DOC-G6")
        self.assertEqual(1, result.returncode)
        self.assertIn("second specification home holds content", result.stdout)
        self.assertIn(".kiro/specs", result.stdout)
        self.assertNotIn("DOC-G6 openspec/specs", result.stdout)

    def test_declared_home_outside_the_candidate_list_is_a_config_error(self) -> None:
        self.policy(spec_homes=HOMES, spec_home="spec")
        result = run(self.root, "DOC-G6")
        self.assertEqual(2, result.returncode)
        self.assertIn("is not listed in spec_homes", result.stderr)

    def test_escaping_home_is_a_config_error(self) -> None:
        self.policy(spec_homes=["../elsewhere"])
        result = run(self.root, "DOC-G6")
        self.assertEqual(2, result.returncode)
        self.assertIn("escapes the repository", result.stderr)


class AbsorptionRecordTests(unittest.TestCase):
    """A retired state document must name what replaced it."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        (self.root / "policy.json").write_text(
            json.dumps(base_policy()), encoding="utf-8"
        )

    def write(self, status: str, *extra: str) -> None:
        document(
            self.root,
            "docs/absorbed.md",
            "id: governance/rules/absorbed",
            "class: state",
            f"status: {status}",
            "owner: test",
            "updated: 2026-08-04",
            "sources: [fixture]",
            *extra,
        )

    def test_superseded_without_a_pointer_fails(self) -> None:
        self.write("superseded")
        result = run(self.root, "DOC-G2")
        self.assertEqual(1, result.returncode)
        self.assertIn("must declare a non-empty superseded_by", result.stdout)

    def test_deprecated_without_a_pointer_fails(self) -> None:
        self.write("deprecated")
        self.assertEqual(1, run(self.root, "DOC-G2").returncode)

    def test_empty_pointer_is_not_a_record(self) -> None:
        self.write("superseded", "superseded_by:")
        self.assertEqual(1, run(self.root, "DOC-G2").returncode)

    def test_naming_the_owner_passes(self) -> None:
        self.write("superseded", "superseded_by: [openspec/specs/billing/spec.md]")
        self.assertEqual(0, run(self.root, "DOC-G2").returncode)

    def test_explicit_empty_list_records_a_retirement(self) -> None:
        self.write("superseded", "superseded_by: []")
        self.assertEqual(0, run(self.root, "DOC-G2").returncode)

    def test_active_document_needs_no_pointer(self) -> None:
        self.write("active")
        self.assertEqual(0, run(self.root, "DOC-G2").returncode)


if __name__ == "__main__":
    unittest.main()
