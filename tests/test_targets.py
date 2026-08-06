#!/usr/bin/env python3
"""Fan-out into per-tool skill roots."""

from __future__ import annotations

import json
import posixpath
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness.py"
MANIFEST = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))
VERSION = MANIFEST["version"]
TARGET_ROOTS = [str(target["root"]) for target in MANIFEST["targets"]]
RELATIVE_LINK = re.compile(r"]\((\.\./[^)]+)\)")


def install(project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    return subprocess.run(
        [
            sys.executable,
            str(HARNESS),
            "init",
            "--project",
            str(project),
            "--source",
            "virusa78/gov-harness",
            "--to",
            VERSION,
            "--from-dir",
            str(ROOT),
            "--profile",
            "spec/openspec",
            "--param",
            "golden_sample=requirements/golden.md",
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


class ManifestShapeTests(unittest.TestCase):
    def test_targets_are_declared(self) -> None:
        self.assertEqual(["agents", "claude", "codex"], [t["name"] for t in MANIFEST["targets"]])

    def test_every_target_root_is_a_managed_root(self) -> None:
        self.assertEqual(sorted(TARGET_ROOTS), sorted(MANIFEST["managed_roots"]))

    def test_skills_fan_out_and_nothing_else_does(self) -> None:
        for item in MANIFEST["files"]:
            destination = str(item["destination"])
            with self.subTest(destination=destination):
                self.assertEqual(
                    item["fanout"], destination.startswith("{{target_root}}/")
                )

    def test_every_target_root_is_two_segments_deep(self) -> None:
        """A skill links its rules as ../../../<path>.

        From <root>/<skill>/SKILL.md that only lands on the project root when
        <root> has exactly two segments. A deeper or shallower root would point
        every rule link outside the project without any error.
        """
        for root in TARGET_ROOTS:
            with self.subTest(root=root):
                self.assertEqual(2, len(root.split("/")), root)


class LinkResolutionTests(unittest.TestCase):
    """The invariant above, checked against the actual shipped link targets."""

    def shipped_destinations(self) -> set[str]:
        """Installed paths, with every fanout destination expanded per root.

        A link may point at a sibling skill, which only exists once the
        target root is substituted; comparing against raw manifest
        destinations would miss it.
        """
        shipped: set[str] = set()
        for item in MANIFEST["files"]:
            destination = str(item["destination"])
            if item["fanout"]:
                suffix = destination.split("/", 1)[1]
                shipped.update(f"{root}/{suffix}" for root in TARGET_ROOTS)
            else:
                shipped.add(destination)
        return shipped

    def test_rule_links_resolve_from_every_target_root(self) -> None:
        shipped = self.shipped_destinations()
        checked = 0
        for item in MANIFEST["files"]:
            if not item["fanout"] or not str(item["source"]).endswith(".md"):
                continue
            text = (ROOT / str(item["source"])).read_text(encoding="utf-8")
            links = RELATIVE_LINK.findall(text)
            suffix = str(item["destination"]).split("/", 1)[1]
            for root in TARGET_ROOTS:
                installed = posixpath.dirname(f"{root}/{suffix}")
                for link in links:
                    resolved = posixpath.normpath(posixpath.join(installed, link))
                    checked += 1
                    with self.subTest(root=root, link=link):
                        self.assertIn(resolved, shipped)
        self.assertGreater(checked, 0, "no relative links were exercised")


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.project = Path(self._temp.name) / "project"

    def roots_present(self) -> list[str]:
        return [root for root in TARGET_ROOTS if (self.project / root).is_dir()]

    def test_default_install_covers_every_target(self) -> None:
        result = install(self.project)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(TARGET_ROOTS, self.roots_present())

    def test_selected_target_installs_only_that_root(self) -> None:
        result = install(self.project, "--target", "codex")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([".codex/skills"], self.roots_present())
        lock = json.loads((self.project / ".harness.lock").read_text(encoding="utf-8"))
        self.assertEqual(["codex"], lock["targets"])

    def test_unknown_target_is_refused(self) -> None:
        result = install(self.project, "--target", "cursor")
        self.assertEqual(3, result.returncode)
        self.assertIn("unknown target(s): cursor", result.stdout + result.stderr)

    def test_the_same_bytes_land_in_every_root(self) -> None:
        install(self.project)
        digests = {
            (self.project / root / "sdd-workflow/SKILL.md").read_bytes()
            for root in TARGET_ROOTS
        }
        self.assertEqual(1, len(digests))

    def test_a_stray_in_any_target_root_is_reported(self) -> None:
        install(self.project)
        stray = self.project / ".codex/skills/handmade"
        stray.mkdir(parents=True)
        (stray / "SKILL.md").write_text("---\nname: handmade\n---\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(self.project / "scripts/harness.py"),
             "check", "--project", str(self.project)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn(".codex/skills/handmade/SKILL.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
