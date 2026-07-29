#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

import harness


HARNESS = Path(__file__).resolve().parents[1] / "harness.py"


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.release = self.root / "release-source"
        self.project = self.root / "project"
        (self.release / "release").mkdir(parents=True)
        (self.release / "core").mkdir()
        (self.release / "profile").mkdir()
        self.project.mkdir()
        (self.release / "core/rule.md").write_text(
            "Golden={{golden_sample}}\n", encoding="utf-8"
        )
        (self.release / "profile/gate.md").write_text(
            "profile\n", encoding="utf-8"
        )
        self.version = "v0.1.0-test"
        self.write_manifest()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_manifest(self) -> None:
        files = [
            {
                "source": "core/rule.md",
                "destination": "docs/governance/rule.md",
                "layer": "core",
                "profile": None,
                "templated": True,
                "sha256": sha((self.release / "core/rule.md").read_bytes()),
            },
            {
                "source": "profile/gate.md",
                "destination": "docs/governance/csharp.md",
                "layer": "profile",
                "profile": "csharp-fintech",
                "templated": False,
                "sha256": sha((self.release / "profile/gate.md").read_bytes()),
            },
        ]
        manifest = {
            "schema_version": 1,
            "version": self.version,
            "required_params": ["golden_sample"],
            "files": files,
        }
        (self.release / "release/manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HARNESS), *arguments],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def init(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
            "init",
            "--project",
            str(self.project),
            "--source",
            "https://github.com/example/harness",
            "--to",
            self.version,
            "--from-dir",
            str(self.release),
            "--profile",
            "csharp-fintech",
            "--param",
            "golden_sample=requirements/golden.md",
            *extra,
        )

    def test_init_check_and_repeated_sync_are_idempotent(self) -> None:
        self.assertEqual(0, self.init().returncode)
        self.assertEqual(0, self.run_cli("check", "--project", str(self.project)).returncode)
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }
        result = self.run_cli(
            "sync",
            "--project",
            str(self.project),
            "--to",
            self.version,
            "--from-dir",
            str(self.release),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        after = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertIn("empty diff", result.stdout)

    def test_check_and_diff_report_drift_with_exit_two(self) -> None:
        self.assertEqual(0, self.init().returncode)
        (self.project / "docs/governance/rule.md").write_text(
            "local drift\n", encoding="utf-8"
        )
        self.assertEqual(2, self.run_cli("check", "--project", str(self.project)).returncode)
        self.assertEqual(2, self.run_cli("diff", "--project", str(self.project)).returncode)

    def test_sync_refuses_drift_without_mutation(self) -> None:
        self.assertEqual(0, self.init().returncode)
        path = self.project / "docs/governance/rule.md"
        path.write_text("local drift\n", encoding="utf-8")
        result = self.run_cli(
            "sync",
            "--project",
            str(self.project),
            "--to",
            self.version,
            "--from-dir",
            str(self.release),
        )
        self.assertEqual(3, result.returncode)
        self.assertEqual("local drift\n", path.read_text(encoding="utf-8"))

    def test_force_theirs_replaces_drift_explicitly(self) -> None:
        self.assertEqual(0, self.init().returncode)
        path = self.project / "docs/governance/rule.md"
        path.write_text("local drift\n", encoding="utf-8")
        result = self.run_cli(
            "sync",
            "--project",
            str(self.project),
            "--to",
            self.version,
            "--from-dir",
            str(self.release),
            "--force-theirs",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "Golden=requirements/golden.md\n", path.read_text(encoding="utf-8")
        )

    def test_sync_accepts_local_bytes_already_adopted_by_target(self) -> None:
        self.assertEqual(0, self.init().returncode)
        target = self.release / "profile/gate.md"
        target.write_text("adopted upstream\n", encoding="utf-8")
        self.write_manifest()
        local = self.project / "docs/governance/csharp.md"
        local.write_text("adopted upstream\n", encoding="utf-8")
        result = self.run_cli(
            "sync",
            "--project",
            str(self.project),
            "--to",
            self.version,
            "--from-dir",
            str(self.release),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0, self.run_cli("check", "--project", str(self.project)).returncode)

    def test_sync_refuses_new_destination_collision(self) -> None:
        self.assertEqual(0, self.init().returncode)
        added = self.release / "core/new-gate.py"
        added.write_text("upstream\n", encoding="utf-8")
        manifest_path = self.release / "release/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"].append(
            {
                "source": "core/new-gate.py",
                "destination": "scripts/new-gate.py",
                "layer": "core",
                "profile": None,
                "templated": False,
                "sha256": sha(added.read_bytes()),
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        local = self.project / "scripts/new-gate.py"
        local.parent.mkdir(parents=True)
        local.write_text("project local\n", encoding="utf-8")
        result = self.run_cli(
            "sync",
            "--project",
            str(self.project),
            "--to",
            self.version,
            "--from-dir",
            str(self.release),
        )
        self.assertEqual(3, result.returncode)
        self.assertIn("collides with an unmanaged local path", result.stderr)
        self.assertEqual("project local\n", local.read_text(encoding="utf-8"))

    def test_sync_accepts_identical_new_destination(self) -> None:
        self.assertEqual(0, self.init().returncode)
        added = self.release / "core/new-gate.py"
        added.write_text("same\n", encoding="utf-8")
        manifest_path = self.release / "release/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"].append(
            {
                "source": "core/new-gate.py",
                "destination": "scripts/new-gate.py",
                "layer": "core",
                "profile": None,
                "templated": False,
                "sha256": sha(added.read_bytes()),
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        local = self.project / "scripts/new-gate.py"
        local.parent.mkdir(parents=True)
        local.write_text("same\n", encoding="utf-8")
        result = self.run_cli(
            "sync",
            "--project",
            str(self.project),
            "--to",
            self.version,
            "--from-dir",
            str(self.release),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0, self.run_cli("check", "--project", str(self.project)).returncode)

    def test_override_is_never_owned_or_modified(self) -> None:
        local = self.project / "docs/governance/rule.md"
        local.parent.mkdir(parents=True)
        local.write_text("project-owned\n", encoding="utf-8")
        result = self.init("--override", "docs/governance/rule.md")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("project-owned\n", local.read_text(encoding="utf-8"))
        lock = json.loads((self.project / ".harness.lock").read_text())
        self.assertNotIn("docs/governance/rule.md", lock["files"])

    def test_adopt_existing_requires_exact_bytes(self) -> None:
        path = self.project / "docs/governance/rule.md"
        path.parent.mkdir(parents=True)
        path.write_text("wrong\n", encoding="utf-8")
        self.assertEqual(3, self.init("--adopt-existing").returncode)
        self.assertFalse((self.project / ".harness.lock").exists())

    def test_adopt_produces_patch_without_changing_lock(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(
            ["git", "config", "user.email", "gate@example.invalid"],
            cwd=self.project,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Gate Test"], cwd=self.project, check=True
        )
        self.assertEqual(0, self.init().returncode)
        subprocess.run(["git", "add", "."], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-qm", "installed"], cwd=self.project, check=True)
        before = (self.project / ".harness.lock").read_bytes()
        path = self.project / "docs/governance/csharp.md"
        path.write_text("improved\n", encoding="utf-8")
        result = self.run_cli(
            "adopt",
            "--project",
            str(self.project),
            "docs/governance/csharp.md",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, (self.project / ".harness.lock").read_bytes())
        patches = list((self.project / ".artifacts/harness-adopt").glob("*.patch"))
        metadata = list((self.project / ".artifacts/harness-adopt").glob("*.json"))
        self.assertEqual(1, len(patches))
        self.assertEqual(1, len(metadata))
        self.assertIn("+improved", patches[0].read_text(encoding="utf-8"))
        self.assertIn("a/profile/gate.md", patches[0].read_text(encoding="utf-8"))
        receipt = json.loads(metadata[0].read_text(encoding="utf-8"))
        self.assertEqual(
            [
                {
                    "destination": "docs/governance/csharp.md",
                    "origin": "profile/gate.md",
                }
            ],
            receipt["mappings"],
        )

    def test_adopt_refuses_rendered_template(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(
            ["git", "config", "user.email", "gate@example.invalid"],
            cwd=self.project,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Gate Test"], cwd=self.project, check=True
        )
        self.assertEqual(0, self.init().returncode)
        subprocess.run(["git", "add", "."], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-qm", "installed"], cwd=self.project, check=True)
        path = self.project / "docs/governance/rule.md"
        path.write_text("cannot reverse template\n", encoding="utf-8")
        result = self.run_cli(
            "adopt",
            "--project",
            str(self.project),
            "docs/governance/rule.md",
        )
        self.assertEqual(3, result.returncode)
        self.assertIn("rendered template", result.stderr)

    def test_manifest_traversal_and_bad_digest_refuse(self) -> None:
        manifest_path = self.release / "release/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][0]["destination"] = "../escape.md"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(3, self.init().returncode)
        self.assertFalse((self.root / "escape.md").exists())
        self.assertFalse((self.project / ".harness.lock").exists())

    def test_partial_apply_failure_rolls_back_every_written_file(self) -> None:
        blocked_source = self.release / "core/blocked.md"
        blocked_source.write_text("blocked\n", encoding="utf-8")
        manifest_path = self.release / "release/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"].append(
            {
                "source": "core/blocked.md",
                "destination": "docs/z-blocked.md",
                "layer": "core",
                "profile": None,
                "templated": False,
                "sha256": sha(blocked_source.read_bytes()),
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (self.project / "docs/z-blocked.md").mkdir(parents=True)
        result = self.init()
        self.assertEqual(3, result.returncode)
        self.assertFalse((self.project / ".harness.lock").exists())
        self.assertFalse((self.project / "docs/governance/rule.md").exists())
        self.assertTrue((self.project / "docs/z-blocked.md").is_dir())

    def test_missing_lock_is_refusal(self) -> None:
        self.assertEqual(
            3, self.run_cli("check", "--project", str(self.project)).returncode
        )

    def test_redirect_drops_authorization_on_host_change(self) -> None:
        request = urllib.request.Request(
            "https://api.github.com/repos/example/release",
            headers={"Authorization": "Bearer secret"},
        )
        redirected = harness.SafeRedirectHandler().redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://objects.githubusercontent.com/signed-asset",
        )
        self.assertIsNotNone(redirected)
        assert redirected is not None
        self.assertIsNone(redirected.get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
