#!/usr/bin/env python3
"""The README says "produces exactly this". That is a testable claim.

It was already wrong before this test existed: the listed install omitted
`verify-evidence.py`, shipped in `v0.8.0-rc.1`. Prose drifts from the manifest
silently, and a consumer following an install listing that under-reports what
lands has no way to notice.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
MANIFEST = ROOT / "release/manifest.json"


def manifest_scripts(layer: str | None = "core") -> set[str]:
    """Scripts the release lands under `scripts/`.

    The core layer is what a minimal install gets; a profile gate such as
    `verify-adr.py` ships only with its profile, so the exit-code table may
    reference it while the minimal-install listing must not.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {
        entry["destination"].split("/", 1)[1]
        for entry in manifest["files"]
        if entry["destination"].startswith("scripts/")
        and (layer is None or entry["layer"] == layer)
    }


def readme_install_block() -> str:
    match = re.search(
        r"A minimal install .*?```text\n(.*?)```", README.read_text(encoding="utf-8"), re.S
    )
    assert match, "the README no longer contains the minimal-install listing"
    return match.group(1)


class InstallListingTests(unittest.TestCase):
    def test_every_shipped_script_is_listed(self) -> None:
        listing = readme_install_block()
        for name in sorted(manifest_scripts()):
            with self.subTest(script=name):
                self.assertIn(name, listing)

    def test_nothing_listed_is_absent_from_the_release(self) -> None:
        listing = readme_install_block()
        shipped = manifest_scripts()
        for name in re.findall(r"[a-z0-9_-]+\.(?:py|sh)", listing):
            with self.subTest(script=name):
                self.assertIn(name, shipped)

    def test_the_rule_count_matches_the_release(self) -> None:
        listing = readme_install_block()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rules = {
            entry["destination"]
            for entry in manifest["files"]
            if entry["destination"].startswith("docs/governance/rules/")
            and entry["layer"] == "core"
        }
        # spec-home.md arrives from the exclusive spec/* profile, so a minimal
        # install lands the core rules plus exactly one variant of it.
        match = re.search(r"rules/ \((\d+) files", listing)
        self.assertIsNotNone(match, listing)
        self.assertEqual(len(rules) + 1, int(match.group(1)))


class ExitCodeTableTests(unittest.TestCase):
    """Every row must name a command the release actually ships."""

    def rows(self) -> list[str]:
        text = README.read_text(encoding="utf-8")
        match = re.search(r"\| Command \| clean \|.*?\n\n", text, re.S)
        assert match, "the README no longer contains the exit-code table"
        return [line for line in match.group(0).splitlines() if line.startswith("| `")]

    def test_each_row_names_a_shipped_script(self) -> None:
        shipped = manifest_scripts(layer=None) | {"harness.py"}
        for row in self.rows():
            names = re.findall(r"[a-z0-9_-]+\.(?:py|sh)", row)
            self.assertTrue(names, row)
            for name in names:
                with self.subTest(row=row, script=name):
                    self.assertIn(name, shipped)

    def test_every_gate_that_can_be_run_standalone_has_a_row(self) -> None:
        documented = " ".join(self.rows())
        for name in sorted(manifest_scripts()):
            if name.endswith(".sh") or name == "harness.py":
                continue  # a wrapper, and the CLI has its own row
            with self.subTest(script=name):
                self.assertIn(name, documented)


if __name__ == "__main__":
    unittest.main()
