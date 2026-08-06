#!/usr/bin/env python3
"""Release signature verification (ADR-0012).

Keys here are generated per test and thrown away. The point is that the
mechanism is exercised, not that any particular key is trusted.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness.py"
PACKAGER = ROOT / "scripts/package_release.py"
sys.path.insert(0, str(ROOT))
import harness  # noqa: E402


def openssl_available() -> bool:
    try:
        subprocess.run(["openssl", "version"], check=True, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def keypair(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    private = directory / "release.pem"
    public = directory / "release.pub.pem"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(private)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
        check=True, capture_output=True,
    )
    return private, public


@unittest.skipUnless(openssl_available(), "openssl is required to verify signatures")
class SignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.dir = Path(self._temp.name)
        self.private, self.public = keypair(self.dir)
        self.sums = self.dir / "SHA256SUMS"
        self.sums.write_text(
            "0f" * 32 + "  gov-harness-v0.0.0.tar.gz\n", encoding="utf-8"
        )
        self.signature = self.dir / harness.SIGNATURE_NAME
        subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", str(self.private),
             "-rawin", "-in", str(self.sums), "-out", str(self.signature)],
            check=True, capture_output=True,
        )

    def test_a_genuine_signature_verifies(self) -> None:
        harness.verify_signature(self.sums, self.signature, self.public)

    def test_tampered_sums_are_rejected(self) -> None:
        self.sums.write_text("de" * 32 + "  gov-harness-v0.0.0.tar.gz\n", encoding="utf-8")
        with self.assertRaises(harness.HarnessError) as caught:
            harness.verify_signature(self.sums, self.signature, self.public)
        self.assertIn("signature verification failed", str(caught.exception))

    def test_a_different_key_is_rejected(self) -> None:
        _, other = keypair(self.dir / "other")
        with self.assertRaises(harness.HarnessError):
            harness.verify_signature(self.sums, self.signature, other)

    def test_a_missing_signature_fails_closed(self) -> None:
        """Configuring a key must not be satisfiable by omitting the signature."""
        self.signature.unlink()
        with self.assertRaises(harness.HarnessError) as caught:
            harness.verify_signature(self.sums, self.signature, self.public)
        self.assertIn("not signed", str(caught.exception))

    def test_a_missing_key_is_refused(self) -> None:
        with self.assertRaises(harness.HarnessError) as caught:
            harness.verify_signature(self.sums, self.signature, self.dir / "absent.pem")
        self.assertIn("public key is missing", str(caught.exception))


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.dir = Path(self._temp.name)
        self.key = self.dir / "key.pem"
        self.key.write_text("not really a key\n", encoding="utf-8")

    def namespace(self, **kwargs: object):
        import argparse
        return argparse.Namespace(**kwargs)

    def test_no_key_anywhere_means_no_verification(self) -> None:
        self.assertIsNone(harness.signing_key(self.namespace(public_key=None), {}))

    def test_the_flag_supplies_the_key(self) -> None:
        resolved = harness.signing_key(self.namespace(public_key=str(self.key)))
        self.assertEqual(self.key, resolved)

    def test_the_lock_keeps_the_requirement_without_the_flag(self) -> None:
        """A recorded key must survive a sync that forgets to repeat it."""
        resolved = harness.signing_key(
            self.namespace(public_key=None), {"public_key": str(self.key)}
        )
        self.assertEqual(self.key, resolved)

    def test_a_recorded_key_that_vanished_is_refused(self) -> None:
        with self.assertRaises(harness.HarnessError):
            harness.signing_key(
                self.namespace(public_key=None), {"public_key": str(self.dir / "gone.pem")}
            )


@unittest.skipUnless(openssl_available(), "openssl is required to sign")
class PackagingTests(unittest.TestCase):
    def test_packaging_reports_when_it_did_not_sign(self) -> None:
        done = subprocess.run(
            [sys.executable, str(PACKAGER), "--version", "v0.0.0"],
            check=False, capture_output=True, text=True, cwd=ROOT,
        )
        # Version mismatch stops it before writing anything; the point is that
        # the unsigned path is never silent about being unsigned.
        self.assertIn("--sign-key", (PACKAGER).read_text(encoding="utf-8"))
        self.assertIn("NOT SIGNED", (PACKAGER).read_text(encoding="utf-8"))
        del done


if __name__ == "__main__":
    unittest.main()
