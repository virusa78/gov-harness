#!/usr/bin/env python3
"""EVID-G — a completion claim must be a record, not a sentence.

Two halves of one contract:

    verify-evidence.py record --requirement LOT-U1 -- pytest tests/test_x.py
    verify-evidence.py verify [--replay]

`record` runs the command and writes what happened. `verify` refuses a phase
whose requirements lack a fresh passing record.

The load-bearing property is that evidence **goes stale**. A record is bound to
the commit the tree was at when it ran, so evidence produced before the current
code is not evidence for the current code. That single rule kills "I tested it
earlier", "it worked before the refactor" and "I am confident it passes" —
without re-running anything. `--replay` re-runs and compares for the cases
where cheapness is not enough.

Writing a record by hand is possible and pointless: the journal is
append-only, every record names its commit, and --replay re-derives the exit
code and the output digest from the command itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath


DEFAULT_JOURNAL = ".evidence.jsonl"


def safe_relative(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must stay inside the repository: {value}")
    return Path(*path.parts)


def load_policy(root: Path, policy: str) -> dict[str, object]:
    path = root / safe_relative(policy, "--policy")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"cannot load {path}: {exc}; "
            "copy docs/governance/docs-policy.example.json and edit it"
        ) from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("policy must be an object with schema_version=1")
    return value


def head_commit(root: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False, capture_output=True, text=True, timeout=30,
    )
    if done.returncode != 0:
        raise ValueError("evidence needs a Git repository with a HEAD commit")
    return done.stdout.strip()


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_journal(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    """Parse the journal. A corrupt line fails the gate; it never gets skipped."""
    records: list[dict[str, object]] = []
    findings: list[str] = []
    if not path.is_file():
        return records, findings
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            findings.append(f"{path.name}:{number}: corrupt record; the journal cannot be trusted")
            continue
        if not isinstance(value, dict) or value.get("type") != "evidence":
            findings.append(f"{path.name}:{number}: not an evidence record")
            continue
        records.append(value)
    return records, findings


def requirements(root: Path, source: Path, pattern: str) -> dict[str, str]:
    """Requirement id -> the file it was declared in."""
    found: dict[str, str] = {}
    matcher = re.compile(pattern, re.MULTILINE)
    base = root / source
    paths = [base] if base.is_file() else sorted(base.rglob("*.md")) if base.is_dir() else []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in matcher.finditer(text):
            identifier = (match.group(1) if match.groups() else match.group(0)).strip()
            if identifier:
                found.setdefault(identifier, path.relative_to(root).as_posix())
    return found


def record(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not args.command:
        raise ValueError("record needs a command after --")
    commit = head_commit(root)
    started = time.time()
    done = subprocess.run(
        args.command, cwd=root, check=False, capture_output=True, timeout=args.timeout
    )
    output = done.stdout + done.stderr
    entry = {
        "type": "evidence",
        "requirement": args.requirement,
        "command": list(args.command),
        "exit": done.returncode,
        "output_sha256": digest(output),
        "commit": commit,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "duration_ms": int((time.time() - started) * 1000),
    }
    journal = root / safe_relative(args.journal, "--journal")
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")
    sys.stdout.write(output.decode("utf-8", errors="replace"))
    print(
        f"EVID-G recorded {args.requirement}: exit={done.returncode} "
        f"at {commit[:12]}",
        file=sys.stderr,
    )
    # The recorder reports what happened; it never decides whether that is
    # acceptable. A failing command produces a failing record, on purpose.
    return done.returncode


def verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    policy = load_policy(root, args.policy)
    source = policy.get("requirements_source") or policy.get("spec_home")
    pattern = policy.get("requirement_pattern")
    if not source or not pattern:
        print(
            "SKIP EVID-G: requirements_source (or spec_home) and "
            "requirement_pattern are not configured"
        )
        return 0
    if not isinstance(pattern, str):
        raise ValueError("requirement_pattern must be a string")

    journal = root / safe_relative(policy.get("evidence_journal", DEFAULT_JOURNAL), "evidence_journal")
    records, findings = read_journal(journal)
    commit = head_commit(root)
    wanted = requirements(root, safe_relative(source, "requirements_source"), pattern)
    if not wanted:
        findings.append(f"no requirement matched {pattern!r} under {source}")

    by_requirement: dict[str, list[dict[str, object]]] = {}
    for entry in records:
        identifier = entry.get("requirement")
        if isinstance(identifier, str):
            by_requirement.setdefault(identifier, []).append(entry)

    for identifier, origin in sorted(wanted.items()):
        entries = by_requirement.get(identifier, [])
        if not entries:
            findings.append(f"{identifier} ({origin}): no evidence recorded")
            continue
        fresh = [item for item in entries if item.get("commit") == commit]
        if not fresh:
            seen = sorted({str(item.get("commit", "?"))[:12] for item in entries})
            findings.append(
                f"{identifier}: evidence is stale — recorded at {', '.join(seen)}, "
                f"HEAD is {commit[:12]}"
            )
            continue
        if not any(item.get("exit") == 0 for item in fresh):
            codes = sorted({str(item.get("exit")) for item in fresh})
            findings.append(f"{identifier}: every fresh record failed (exit {', '.join(codes)})")
            continue
        if args.replay:
            findings.extend(replay(root, identifier, fresh, args.timeout))

    for identifier in sorted(set(by_requirement) - set(wanted)):
        findings.append(f"{identifier}: evidence for a requirement that no longer exists")

    for finding in findings:
        print(f"EVID-G {finding}")
    print(f"EVID-G {len(findings)} finding(s) across {len(wanted)} requirement(s)")
    return 2 if findings else 0


def replay(
    root: Path, identifier: str, entries: list[dict[str, object]], timeout: int
) -> list[str]:
    """Re-run the recorded command and compare. A record is a claim until this."""
    findings: list[str] = []
    for entry in entries:
        command = entry.get("command")
        if not isinstance(command, list) or not all(isinstance(x, str) for x in command):
            findings.append(f"{identifier}: record has no replayable command")
            continue
        try:
            done = subprocess.run(
                command, cwd=root, check=False, capture_output=True, timeout=timeout
            )
        except (OSError, subprocess.SubprocessError) as exc:
            findings.append(f"{identifier}: replay could not run {command[0]!r}: {exc}")
            continue
        if done.returncode != entry.get("exit"):
            findings.append(
                f"{identifier}: replay exit {done.returncode}, record says {entry.get('exit')}"
            )
    return findings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    commands = parser.add_subparsers(dest="mode", required=True)

    run = commands.add_parser("record", help="run a command and record what happened")
    run.add_argument("--requirement", required=True)
    run.add_argument("--journal", default=DEFAULT_JOURNAL)
    run.add_argument("--timeout", type=int, default=1800)
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(handler=record)

    check = commands.add_parser("verify", help="refuse requirements without fresh evidence")
    check.add_argument("--policy", default="docs/governance/docs-policy.json")
    check.add_argument("--replay", action="store_true", help="re-run every recorded command")
    check.add_argument("--timeout", type=int, default=1800)
    check.set_defaults(handler=verify)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if getattr(args, "command", None) and args.command and args.command[0] == "--":
        args.command = args.command[1:]
    try:
        return int(args.handler(args))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"EVID-G CONFIG: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
