#!/usr/bin/env python3
"""Build a deterministic release archive and SHA256SUMS."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def archive(version: str) -> tuple[Path, Path]:
    manifest_path = ROOT / "release/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != version:
        raise RuntimeError(
            f"manifest version {manifest.get('version')!r} does not match {version!r}"
        )
    sources = sorted(
        {str(item["source"]) for item in manifest["files"]} | {"release/manifest.json"}
    )
    output = ROOT / "dist" / f"gov-harness-{version}.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as bundle:
                for relative in sources:
                    path = ROOT / relative
                    data = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(data)
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mode = 0o755 if path.suffix in {".py", ".sh"} else 0o644
                    bundle.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sums = ROOT / "dist/SHA256SUMS"
    sums.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output, sums


def sign(sums: Path, key: Path) -> Path:
    """Sign SHA256SUMS with an Ed25519 private key (ADR-0012).

    SHA256SUMS names the archive and its digest, so one signature covers the
    release. The private key never enters this repository; it is named on the
    command line by whoever cuts the release.
    """
    signature = sums.with_name(sums.name + ".sig")
    subprocess.run(
        [
            "openssl", "pkeyutl", "-sign", "-inkey", str(key),
            "-rawin", "-in", str(sums), "-out", str(signature),
        ],
        check=True,
        capture_output=True,
    )
    return signature


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--sign-key",
        help="Ed25519 private key (PEM) used to sign SHA256SUMS",
    )
    args = parser.parse_args()
    output, sums = archive(args.version)
    print(output.relative_to(ROOT))
    print(sums.relative_to(ROOT))
    if args.sign_key:
        signature = sign(sums, Path(args.sign_key).expanduser())
        print(signature.relative_to(ROOT))
    else:
        print("NOT SIGNED: pass --sign-key to produce SHA256SUMS.sig", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

