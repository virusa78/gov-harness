#!/usr/bin/env python3
"""A lock that cannot be synced from is a defect created at install time.

`init` used to store `--source` verbatim and never look at it, because
`--from-dir` does not consult it. The consumer learned their source was
unusable at the first network sync, which could be months later and in a
different session, and the message named the source format rather than the
install that produced it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harness  # noqa: E402


class NormalizationTests(unittest.TestCase):
    CANONICAL = "https://github.com/virusa78/gov-harness"

    def test_both_documented_spellings_reach_the_same_source(self) -> None:
        for spelling in (
            "virusa78/gov-harness",
            "https://github.com/virusa78/gov-harness",
            "https://github.com/virusa78/gov-harness.git",
            "virusa78/gov-harness/",
        ):
            with self.subTest(spelling=spelling):
                self.assertEqual(self.CANONICAL, harness.normalize_source(spelling))

    def test_owner_and_repo_survive_legal_punctuation(self) -> None:
        self.assertEqual(
            "https://github.com/Some-Org/repo.name_v2",
            harness.normalize_source("Some-Org/repo.name_v2"),
        )

    def test_an_ssh_remote_is_refused(self) -> None:
        """It splits into two non-empty parts, so only a charset check stops it."""
        with self.assertRaises(harness.HarnessError):
            harness.normalize_source("git@github.com:virusa78/gov-harness.git")

    def test_other_hosts_are_refused(self) -> None:
        for value in ("https://gitlab.com/a/b", "ssh://x/y", "http://github.com/a/b"):
            with self.subTest(value=value):
                with self.assertRaises(harness.HarnessError):
                    harness.normalize_source(value)

    def test_malformed_shorthand_is_refused(self) -> None:
        for value in ("gov-harness", "a/b/c", "owner/", "/repo", "owner/re po", "-x/y"):
            with self.subTest(value=value):
                with self.assertRaises(harness.HarnessError):
                    harness.normalize_source(value)

    def test_the_refusal_quotes_what_was_given(self) -> None:
        with self.assertRaises(harness.HarnessError) as caught:
            harness.normalize_source("https://gitlab.com/a/b")
        self.assertIn("https://gitlab.com/a/b", str(caught.exception))

    def test_the_network_path_accepts_both_spellings(self) -> None:
        """Locks written under the old short form must keep working."""
        for spelling in ("virusa78/gov-harness", "https://github.com/virusa78/gov-harness"):
            with self.subTest(spelling=spelling):
                self.assertEqual(
                    ("virusa78", "gov-harness"), harness.parse_source_repo(spelling)
                )


class InstallTests(unittest.TestCase):
    """The whole point is that this fails at install, not months later."""

    def install(self, project: Path, source: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable, str(ROOT / "harness.py"), "init",
                "--project", str(project),
                "--source", source,
                "--to", "v0.9.0-rc.1",
                "--from-dir", str(ROOT),
                "--profile", "spec/openspec",
                "--param", "golden_sample=requirements/golden.md",
            ],
            check=False, capture_output=True, text=True,
        )

    def setUp(self) -> None:
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "requirements").mkdir()
        (self.project / "requirements/golden.md").write_text("# golden\n", encoding="utf-8")
        self.addCleanup(self.tmp.cleanup)

    def test_the_shorthand_is_recorded_canonically(self) -> None:
        done = self.install(self.project, "virusa78/gov-harness")
        self.assertEqual(0, done.returncode, done.stderr)
        lock = json.loads((self.project / ".harness.lock").read_text(encoding="utf-8"))
        self.assertEqual("https://github.com/virusa78/gov-harness", lock["source"])

    def test_an_unusable_source_is_refused_before_anything_is_written(self) -> None:
        done = self.install(self.project, "git@github.com:virusa78/gov-harness.git")
        self.assertNotEqual(0, done.returncode)
        self.assertFalse(
            (self.project / ".harness.lock").exists(),
            "a refused install must leave no lock behind",
        )
        self.assertFalse(
            (self.project / "docs/governance").exists(),
            "a refused install must write no governed files",
        )


if __name__ == "__main__":
    unittest.main()
