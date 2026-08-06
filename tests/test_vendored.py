#!/usr/bin/env python3
"""Vendored foreign content: pinning, provenance and static composition."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness.py"
VENDOR = ROOT / "vendor"
MANIFEST = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))
VERSION = MANIFEST["version"]
UPSTREAMS = {str(item["name"]): item for item in MANIFEST["upstreams"]}
VENDORED_FILES = [item for item in MANIFEST["files"] if item.get("upstream")]
COMMIT = re.compile(r"^[0-9a-f]{40}$")
# The plugin namespace only resolves when the upstream plugin is installed.
NAMESPACE = re.compile(r"superpowers:[a-z][a-z0-9-]*")


class ProvenanceTests(unittest.TestCase):
    def test_manifest_is_schema_three(self) -> None:
        self.assertEqual(3, MANIFEST["schema_version"])

    def test_every_upstream_pins_a_commit_and_a_license(self) -> None:
        self.assertTrue(UPSTREAMS)
        for name, item in sorted(UPSTREAMS.items()):
            with self.subTest(upstream=name):
                self.assertRegex(str(item["commit"]), COMMIT)
                self.assertTrue(str(item["license"]))
                self.assertTrue(str(item["repo"]).startswith("https://"))

    def test_every_vendored_file_declares_its_origin(self) -> None:
        self.assertTrue(VENDORED_FILES)
        for item in VENDORED_FILES:
            with self.subTest(destination=item["destination"]):
                self.assertIn(item["upstream"], UPSTREAMS)
                self.assertTrue(str(item["upstream_path"]))
                self.assertTrue(str(item["upstream_sha256"]).startswith("sha256:"))
                # Foreign bytes are never core and never templated: rendering
                # them would be a patch nobody recorded.
                self.assertEqual("profile", item["layer"])
                self.assertFalse(item["templated"])

    def test_shipped_digest_matches_the_vendored_bytes(self) -> None:
        for item in VENDORED_FILES:
            data = (ROOT / str(item["source"])).read_bytes()
            with self.subTest(source=item["source"]):
                self.assertEqual(
                    "sha256:" + hashlib.sha256(data).hexdigest(), item["sha256"]
                )

    def test_a_patch_is_visible_as_a_differing_digest(self) -> None:
        """ADR-0011: a local change to foreign content is recorded, not silent."""
        patched = [i for i in VENDORED_FILES if i["sha256"] != i["upstream_sha256"]]
        self.assertTrue(patched, "expected the namespace rewrite to be recorded")
        for item in patched:
            with self.subTest(source=item["source"]):
                text = (ROOT / str(item["source"])).read_text(encoding="utf-8")
                self.assertNotRegex(text, NAMESPACE)

    def test_no_vendored_skill_invokes_the_upstream_plugin_namespace(self) -> None:
        for item in VENDORED_FILES:
            path = ROOT / str(item["source"])
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            with self.subTest(source=item["source"]):
                self.assertNotRegex(text, NAMESPACE)

    def test_the_vendored_set_is_closed_under_cross_references(self) -> None:
        """A shipped skill may not point at a capability we do not ship."""
        shipped = {
            str(item["destination"]).split("/")[1]
            for item in VENDORED_FILES
            if item["fanout"]
        }
        for item in VENDORED_FILES:
            path = ROOT / str(item["source"])
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for referenced in re.findall(r"(?m)^\s*-?\s*Use (?:the )?`?([a-z][a-z0-9-]{4,})`? skill", text):
                if referenced in shipped:
                    continue
                with self.subTest(source=item["source"], skill=referenced):
                    self.assertNotIn(
                        referenced,
                        {"test-driven-development", "verification-before-completion",
                         "writing-skills", "systematic-debugging", "executing-plans"},
                        "references an upstream skill this release does not vendor",
                    )

    def test_license_travels_with_the_bytes(self) -> None:
        destinations = {str(item["destination"]) for item in MANIFEST["files"]}
        for name in UPSTREAMS:
            with self.subTest(upstream=name):
                self.assertIn(f"docs/governance/licenses/{name}.LICENSE", destinations)


class RecordTests(unittest.TestCase):
    def test_offline_check_passes(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts/vendor_upstream.py"), "check"],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(0, done.returncode, done.stderr)

    def test_record_and_manifest_agree(self) -> None:
        for name in UPSTREAMS:
            record = json.loads((VENDOR / name / "UPSTREAM.json").read_text(encoding="utf-8"))
            self.assertEqual(record["commit"], UPSTREAMS[name]["commit"])
            for item in (i for i in VENDORED_FILES if i["upstream"] == name):
                path = str(item["upstream_path"])
                with self.subTest(upstream=name, path=path):
                    self.assertEqual(record["files"][path]["sha256"], item["upstream_sha256"])
                    self.assertEqual(record["files"][path]["executable"], item["executable"])


class InstallTests(unittest.TestCase):
    def test_vendored_profile_installs_with_a_clean_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            done = subprocess.run(
                [sys.executable, str(HARNESS), "init", "--project", str(project),
                 "--source", "virusa78/gov-harness", "--to", VERSION,
                 "--from-dir", str(ROOT), "--profile", "workflow/superpowers",
                 "--param", "golden_sample=requirements/golden.md"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(0, done.returncode, done.stderr + done.stdout)
            self.assertTrue(
                (project / ".claude/skills/using-git-worktrees/SKILL.md").is_file()
            )
            self.assertTrue(
                (project / "docs/governance/licenses/superpowers.LICENSE").is_file()
            )
            # ADR-0005: executable mode is part of the receipt, and upstream
            # ships helper scripts with no suffix to infer it from.
            script = project / ".claude/skills/subagent-driven-development/scripts/task-brief"
            self.assertTrue(script.stat().st_mode & 0o111, "lost the executable bit")
            check = subprocess.run(
                [sys.executable, str(project / "scripts/harness.py"),
                 "check", "--project", str(project)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(0, check.returncode, check.stdout)

    def test_the_installer_never_reaches_an_upstream(self) -> None:
        """Static composition: no upstream host appears in installer code."""
        source = HARNESS.read_text(encoding="utf-8")
        for name, item in UPSTREAMS.items():
            with self.subTest(upstream=name):
                self.assertNotIn(str(item["repo"]), source)


if __name__ == "__main__":
    unittest.main()
