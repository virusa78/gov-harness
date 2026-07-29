#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).resolve().parents[1] / "core/gates/governance_docs.py"


class GeneratedLifecycleTests(unittest.TestCase):
    def test_generated_document_requires_generator_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "docs/generated.md"
            generated.parent.mkdir()
            generated.write_text(
                "---\n"
                "id: generated/test\n"
                "class: generated\n"
                "status: current\n"
                "owner: test\n"
                "updated: 2026-07-29\n"
                "sources: [fixture]\n"
                "---\n",
                encoding="utf-8",
            )
            policy = {
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
            (root / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
            command = [
                sys.executable,
                str(CHECKER),
                "--root",
                str(root),
                "--config",
                "policy.json",
                "--mode",
                "block",
                "--gate",
                "DOC-G2",
            ]
            failed = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(1, failed.returncode)
            self.assertIn("generated document is missing", failed.stdout)
            generated.write_text(
                generated.read_text().replace(
                    "---\n",
                    "---\ngenerator: scripts/generate.py\n"
                    "source_digest: sha256:abc\n",
                    1,
                ),
                encoding="utf-8",
            )
            passed = subprocess.run(command, check=False)
            self.assertEqual(0, passed.returncode)


if __name__ == "__main__":
    unittest.main()
