#!/usr/bin/env python3
"""Guard the release version pinned in CI and documentation.

The reproducibility check takes the expected version as an argument, so a
forgotten bump turns the check into a permanent failure that only a running
runner would surface. This test makes the drift visible offline instead.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release/manifest.json"
PINNED = re.compile(r"build_manifest\.py\s+--version\s+(\S+)")
# Every file that names the release version in a build_manifest invocation.
PIN_SOURCES = (
    ".github/workflows/ci.yml",
    "README.md",
)


class ReleasePinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]

    def test_manifest_declares_a_release_candidate(self) -> None:
        self.assertRegex(self.version, r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")

    def test_every_pin_matches_the_manifest(self) -> None:
        for name in PIN_SOURCES:
            path = ROOT / name
            with self.subTest(source=name):
                self.assertTrue(path.is_file(), f"missing pin source: {name}")
                pins = PINNED.findall(path.read_text(encoding="utf-8"))
                self.assertTrue(pins, f"{name} no longer pins a release version")
                for pin in pins:
                    self.assertEqual(
                        pin,
                        self.version,
                        f"{name} pins {pin}, release/manifest.json declares "
                        f"{self.version}",
                    )


if __name__ == "__main__":
    unittest.main()
