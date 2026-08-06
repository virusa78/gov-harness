#!/usr/bin/env python3
"""Vendor foreign content into the source tree, pinned to a commit (ADR-0011).

This is a maintainer tool. It runs here, never in a consumer project, and the
installer never calls it: `harness.py` gains no network behaviour from this
file existing. Refreshing an upstream produces an ordinary diff that lands
through ordinary review, which is what keeps a refresh from being a blind bulk
update.

    vendor_upstream.py fetch  --upstream superpowers --commit <sha>
    vendor_upstream.py check  [--upstream superpowers]

`fetch` needs the network. `check` never does: it re-derives every digest from
the vendored bytes and the recorded upstream digests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
RECORD = "UPSTREAM.json"
COMMIT = re.compile(r"^[0-9a-f]{40}$")

# Upstreams this repository vendors. Adding one is a reviewed change, not a
# command-line argument, so the set of foreign sources is visible in the diff.
UPSTREAMS: dict[str, dict[str, object]] = {
    "superpowers": {
        "repo": "https://github.com/obra/superpowers",
        "license": "MIT",
        "license_path": "LICENSE",
        "profile": "workflow/superpowers",
        # Closed under cross-skill references: every `superpowers:<name>` these
        # files mention is also in this list. An unclosed set would ship a
        # skill pointing at a capability the consumer never receives.
        "paths": [
            "skills/dispatching-parallel-agents",
            "skills/finishing-a-development-branch",
            "skills/receiving-code-review",
            "skills/requesting-code-review",
            "skills/subagent-driven-development",
            "skills/using-git-worktrees",
        ],
    }
}

# Upstream addresses sibling skills through its plugin namespace. Installed as
# plain skills that namespace does not exist, so the reference is rewritten to
# the bare skill name. Every rewrite shows up as a differing shipped digest.
NAMESPACE = re.compile(r"superpowers:(?=[a-z][a-z0-9-]*)")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def patch(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return NAMESPACE.sub("", text).encode("utf-8")


def git(*args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=300
    )
    return done.stdout


def fetch(name: str, commit: str) -> int:
    spec = UPSTREAMS[name]
    if not COMMIT.fullmatch(commit):
        raise SystemExit(f"commit must be a full 40-hex sha, got {commit!r}")
    destination = VENDOR / name
    with tempfile.TemporaryDirectory() as directory:
        clone = Path(directory) / "src"
        git("clone", "--quiet", str(spec["repo"]), str(clone))
        git("checkout", "--quiet", commit, cwd=clone)
        actual = git("rev-parse", "HEAD", cwd=clone).strip()
        if actual != commit:
            raise SystemExit(f"checkout landed on {actual}, expected {commit}")

        license_path = str(spec["license_path"])
        if not (clone / license_path).is_file():
            raise SystemExit(f"{name}: declared license file is missing upstream")

        if destination.exists():
            shutil.rmtree(destination)
        files: dict[str, str] = {}
        sources = [license_path]
        for entry in spec["paths"]:  # type: ignore[union-attr]
            base = clone / str(entry)
            if not base.is_dir():
                raise SystemExit(f"{name}: vendored path is missing upstream: {entry}")
            sources.extend(
                sorted(
                    path.relative_to(clone).as_posix()
                    for path in base.rglob("*")
                    if path.is_file()
                )
            )
        for relative in sources:
            source = clone / relative
            data = source.read_bytes()
            # ADR-0005 puts executable mode inside the receipt, and upstream
            # ships helper scripts with no suffix to infer it from.
            executable = bool(source.stat().st_mode & 0o111)
            files[relative] = {"sha256": digest(data), "executable": executable}
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(patch(data))
            target.chmod(0o755 if executable else 0o644)

    record = {
        "schema_version": 1,
        "name": name,
        "repo": spec["repo"],
        "commit": commit,
        "license": spec["license"],
        "license_path": license_path,
        "profile": spec["profile"],
        "files": files,
    }
    (destination / RECORD).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    patched = sum(
        1
        for relative, entry in files.items()
        if digest((destination / relative).read_bytes()) != entry["sha256"]
    )
    print(f"vendored {name}@{commit[:12]}: {len(files)} file(s), {patched} patched")
    return 0


def load_record(name: str) -> dict[str, object]:
    path = VENDOR / name / RECORD
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{name}: cannot read {RECORD}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise SystemExit(f"{name}: {RECORD} must be an object with schema_version=1")
    return value


def check(names: list[str]) -> int:
    findings: list[str] = []
    for name in names:
        record = load_record(name)
        if record.get("name") != name:
            findings.append(f"{name}: record names {record.get('name')!r}")
        commit = str(record.get("commit", ""))
        if not COMMIT.fullmatch(commit):
            findings.append(f"{name}: commit is not a full 40-hex sha: {commit!r}")
        license_path = str(record.get("license_path", ""))
        if not license_path or not (VENDOR / name / license_path).is_file():
            findings.append(f"{name}: vendored license file is missing")
        files = record.get("files")
        if not isinstance(files, dict):
            raise SystemExit(f"{name}: {RECORD} files must be an object")

        recorded = {PurePosixPath(item) for item in files}
        present = {
            path.relative_to(VENDOR / name)
            for path in (VENDOR / name).rglob("*")
            if path.is_file() and path.name != RECORD
        }
        for extra in sorted(present - {Path(*item.parts) for item in recorded}):
            findings.append(f"{name}: vendored file is not in {RECORD}: {extra}")
        patched = 0
        for relative, entry in sorted(files.items()):
            path = VENDOR / name / relative
            if not isinstance(entry, dict) or "sha256" not in entry:
                findings.append(f"{name}: malformed record entry: {relative}")
                continue
            if not path.is_file():
                findings.append(f"{name}: recorded file is missing: {relative}")
                continue
            if digest(path.read_bytes()) != entry["sha256"]:
                patched += 1
            if bool(path.stat().st_mode & 0o111) != bool(entry.get("executable")):
                findings.append(f"{name}: executable mode differs from upstream: {relative}")
        print(f"{name}@{commit[:12]}: {len(files)} vendored, {patched} carrying a local patch")
    for finding in findings:
        print(f"VENDOR {finding}", file=sys.stderr)
    return 2 if findings else 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    grab = commands.add_parser("fetch", help="re-vendor an upstream at a commit")
    grab.add_argument("--upstream", required=True, choices=sorted(UPSTREAMS))
    grab.add_argument("--commit", required=True)
    verify = commands.add_parser("check", help="offline consistency check")
    verify.add_argument("--upstream", choices=sorted(UPSTREAMS))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.command == "fetch":
        return fetch(args.upstream, args.commit)
    return check([args.upstream] if args.upstream else sorted(UPSTREAMS))


if __name__ == "__main__":
    raise SystemExit(main())
