#!/usr/bin/env python3
"""A private key must never reach this repository.

Committing one voids every signature it ever made, and git history keeps it
forever. The verifier refuses the whole tree rather than any one path.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts/verify_source.py"
sys.path.insert(0, str(ROOT / "scripts"))
import verify_source  # noqa: E402


def run() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER)], check=False, capture_output=True, text=True
    )


class PrivateKeyGuardTests(unittest.TestCase):
    def test_the_repository_is_clean(self) -> None:
        self.assertEqual(0, run().returncode, run().stderr)

    def test_the_guard_does_not_match_itself(self) -> None:
        """The markers are assembled, so the verifier is not its own finding."""
        text = VERIFIER.read_text(encoding="utf-8")
        for marker in verify_source.PRIVATE_KEY_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

    def test_every_common_key_format_is_covered(self) -> None:
        kinds = " ".join(verify_source.PRIVATE_KEY_MARKERS)
        for expected in ("RSA", "OPENSSH", "EC", "DSA", "PGP"):
            with self.subTest(kind=expected):
                self.assertIn(expected, kinds)

    def test_a_committed_private_key_fails_the_tree(self) -> None:
        planted = ROOT / "core/rules/planted-key.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(planted)],
            check=True, capture_output=True,
        )
        try:
            done = run()
            self.assertEqual(1, done.returncode)
            self.assertIn("private key material", done.stderr)
        finally:
            planted.unlink(missing_ok=True)
        self.assertEqual(0, run().returncode, "cleanup left the tree dirty")

    def test_a_public_key_is_allowed(self) -> None:
        """The public half is meant to be published here (docs/SIGNING.md)."""
        private = ROOT / "tmp-key.pem"
        public = ROOT / "tmp-key.pub.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(private)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
            check=True, capture_output=True,
        )
        private.unlink()
        try:
            self.assertEqual(0, run().returncode)
        finally:
            public.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
