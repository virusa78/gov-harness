#!/usr/bin/env python3
"""ADR-G — the gate the adr profile promises must exist and must bite."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "profiles/adr/gates/verify_adr.py"

RECORD = """# ADR-{number}: {title}

## Status

Accepted — 2026-08-04

## Context

Something forced a decision.

## Decision

We decided.

## Consequences

Things follow.
"""

LESSONS = """# Lessons

## L1 — something bit us (2026-08-04)

Symptom: it broke.

Rule: do not do that again.
"""


def run(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(root), *extra],
        check=False,
        capture_output=True,
        text=True,
    )


class AdrGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        self.decisions = self.root / "docs/architecture/decisions"
        self.decisions.mkdir(parents=True)
        self.write_record("0001", "first", "0001-first.md")
        self.index(["0001-first.md"])
        (self.root / "docs/LESSONS.md").write_text(LESSONS, encoding="utf-8")

    def write_record(self, number: str, title: str, name: str, body: str = RECORD) -> Path:
        path = self.decisions / name
        path.write_text(body.format(number=number, title=title), encoding="utf-8")
        return path

    def index(self, names: list[str]) -> None:
        rows = "\n".join(f"| [ADR]({name}) | decision |" for name in names)
        (self.decisions / "README.md").write_text(
            f"# Decisions\n\n| ADR | Decision |\n|---|---|\n{rows}\n", encoding="utf-8"
        )

    def test_clean_repository_passes(self) -> None:
        result = run(self.root)
        self.assertEqual(0, result.returncode, result.stdout)

    def test_duplicate_decision_number(self) -> None:
        self.write_record("0001", "again", "0001-again.md")
        self.index(["0001-first.md", "0001-again.md"])
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("duplicate decision number 0001", result.stdout)

    def test_missing_required_section(self) -> None:
        self.write_record(
            "0002", "second", "0002-second.md", "# ADR-{number}: {title}\n\n## Status\n\nok\n"
        )
        self.index(["0001-first.md", "0002-second.md"])
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("missing required section 'Context'", result.stdout)

    def test_empty_required_section(self) -> None:
        self.write_record(
            "0002",
            "second",
            "0002-second.md",
            "# ADR-{number}: {title}\n\n## Status\n\n## Context\n\nc\n"
            "## Decision\n\nd\n\n## Consequences\n\ne\n",
        )
        self.index(["0001-first.md", "0002-second.md"])
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("section 'Status' is empty", result.stdout)

    def test_decision_missing_from_index(self) -> None:
        self.write_record("0002", "second", "0002-second.md")
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("decision missing from the index: 0002-second.md", result.stdout)

    def test_index_links_a_phantom_decision(self) -> None:
        self.index(["0001-first.md", "0009-phantom.md"])
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("index links a decision that does not exist", result.stdout)

    def test_lesson_without_a_rule(self) -> None:
        (self.root / "docs/LESSONS.md").write_text(
            "# Lessons\n\n## L1 — it bit us (2026-08-04)\n\nSymptom: broke.\n",
            encoding="utf-8",
        )
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("has no 'Rule:' line", result.stdout)

    def test_lesson_with_an_empty_rule(self) -> None:
        (self.root / "docs/LESSONS.md").write_text(
            "# Lessons\n\n## L1 — it bit us (2026-08-04)\n\nRule:\n", encoding="utf-8"
        )
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("empty 'Rule:' line", result.stdout)

    def test_section_and_field_names_are_configurable(self) -> None:
        """The gate must not impose a language on a repository's canon."""
        self.write_record(
            "0002",
            "second",
            "0002-second.md",
            "# ADR-{number}: {title}\n\n## Статус\n\nПринято\n\n## Решение\n\nРешили\n",
        )
        self.index(["0001-first.md", "0002-second.md"])
        (self.root / "docs/LESSONS.md").write_text(
            "# Уроки\n\n## L1 — сломалось (2026-08-04)\n\nПравило: больше так не делать.\n",
            encoding="utf-8",
        )
        result = run(
            self.root,
            "--section",
            "Статус",
            "--section",
            "Решение",
            "--lesson-field",
            "Правило:",
        )
        # 0001 uses English headings, so it is the only expected offender.
        self.assertEqual(2, result.returncode)
        self.assertIn("0001-first.md: missing required section 'Статус'", result.stdout)
        self.assertNotIn("0002-second.md", result.stdout)

    def test_an_absent_default_directory_skips(self) -> None:
        """Installing the profile is not yet using it.

        A project that has written no decisions has nothing to be wrong about,
        and a gate that is red from the first minute teaches people to ignore
        it.
        """
        shutil.rmtree(self.decisions)
        result = run(self.root)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("SKIP ADR-G", result.stderr)

    def test_an_absent_explicit_directory_is_a_config_error(self) -> None:
        """--decisions asserts a path; a path that is not there is an error."""
        shutil.rmtree(self.decisions)
        result = run(self.root, "--decisions", "docs/adr")
        self.assertEqual(2, result.returncode)
        self.assertIn("ADR-G CONFIG", result.stderr)

    def test_an_empty_default_directory_activates_the_gate(self) -> None:
        """Creating the directory is the act that switches the gate on."""
        for path in self.decisions.iterdir():
            path.unlink()
        result = run(self.root)
        self.assertEqual(2, result.returncode)
        self.assertNotIn("SKIP ADR-G", result.stderr)


class HarnessOwnRecordsTests(unittest.TestCase):
    def test_this_repository_satisfies_its_own_adr_gate(self) -> None:
        result = run(ROOT)
        self.assertEqual(0, result.returncode, result.stdout)


if __name__ == "__main__":
    unittest.main()
