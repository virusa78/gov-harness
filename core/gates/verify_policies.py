#!/usr/bin/env python3
"""POLICY-G: a project's policy copy must stay abreast of the shipped example.

Every gate here is configured by a file the project owns: it copies
`X.example.json` once, edits it, and the harness never touches the copy again.
That ownership is deliberate — the alternative is the harness overwriting the
consumer's configuration — but it has a failure mode nobody was watching.

When a release adds a capability, it adds a key to the example. The copy, being
project-owned, does not gain it. The gate reading the copy sees no key, treats
the capability as unconfigured, and reports clean. The project is told nothing.
An upgrade across four versions can deliver a feature the consumer never learns
exists, and every check stays green the whole way.

This gate compares the two and makes that silence impossible. It does not
demand the copy adopt anything: a project may decline a key by listing it in
`_declined`. Declining is a decision and leaves a trace; not knowing is neither.

    verify-policies.py [--root .] [--policies docs/governance]

Exit codes:
    0  every copy accounts for every key its example defines
    2  a copy is behind its example, or declines something that no longer exists
    3  configuration error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath


SUFFIX = ".example.json"
DECLINED = "_declined"


def safe_relative(raw: str, label: str) -> PurePosixPath:
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe {label}: {raw!r}")
    return path


def public_keys(document: dict) -> set[str]:
    """Keys the gates actually read. `_`-prefixed keys are commentary."""
    return {key for key in document if not key.startswith("_")}


def declined_keys(document: dict, label: str) -> set[str]:
    raw = document.get(DECLINED, [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{label}: {DECLINED} must be a list of strings")
    return set(raw)


def compare(example: dict, copy: dict, copy_label: str) -> list[str]:
    """Report every key the copy neither carries nor consciously declines."""
    findings: list[str] = []
    offered = public_keys(example)
    held = public_keys(copy)
    declined = declined_keys(copy, copy_label)

    for key in sorted(offered - held - declined):
        findings.append(
            f"{copy_label}: the example defines {key!r} and this copy has "
            f"neither the key nor {DECLINED} entry for it — a capability this "
            "project has not been told about"
        )
    for key in sorted(held - offered):
        findings.append(
            f"{copy_label}: has {key!r}, which the example does not define — "
            "a typo, or a key the release removed"
        )
    for key in sorted(declined & held):
        findings.append(
            f"{copy_label}: {key!r} is both configured and listed in "
            f"{DECLINED}; the two disagree about whether it is wanted"
        )
    for key in sorted(declined - offered):
        findings.append(
            f"{copy_label}: declines {key!r}, which the example no longer "
            f"defines — remove it from {DECLINED}"
        )

    example_schema = example.get("schema_version")
    copy_schema = copy.get("schema_version")
    if example_schema is not None and copy_schema != example_schema:
        findings.append(
            f"{copy_label}: schema_version is {copy_schema!r}, the example is "
            f"{example_schema!r}"
        )
    return findings


def load(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return document


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--policies", default="docs/governance")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).resolve()
    try:
        policies = root / safe_relative(args.policies, "--policies")
    except ValueError as exc:
        print(f"POLICY-G CONFIG: {exc}", file=sys.stderr)
        return 3
    if not policies.is_dir():
        print(
            f"SKIP POLICY-G: {args.policies} does not exist, so no policies "
            "are installed here.",
            file=sys.stderr,
        )
        return 0

    examples = sorted(policies.glob(f"*{SUFFIX}"))
    if not examples:
        print(
            f"SKIP POLICY-G: no *{SUFFIX} under {args.policies}.",
            file=sys.stderr,
        )
        return 0

    findings: list[str] = []
    compared = 0
    for example_path in examples:
        copy_path = example_path.with_name(
            example_path.name[: -len(SUFFIX)] + ".json"
        )
        if not copy_path.is_file():
            # Not adopting a gate is a legitimate state, and the gate itself
            # already says "copy the example" when it is asked to run.
            continue
        try:
            example = load(example_path)
            copy = load(copy_path)
            findings.extend(compare(example, copy, copy_path.name))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"POLICY-G CONFIG: {exc}", file=sys.stderr)
            return 3
        compared += 1

    for finding in findings:
        print(f"POLICY-G {finding}")
    print(f"POLICY-G {len(findings)} finding(s) across {compared} policy copy/copies")
    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
