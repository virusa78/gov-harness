#!/usr/bin/env python3
"""Build a deterministic release archive and SHA256SUMS."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    output, sums = archive(args.version)
    print(output.relative_to(ROOT))
    print(sums.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

