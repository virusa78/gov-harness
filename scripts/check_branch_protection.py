#!/usr/bin/env python3
"""Verify that the live branch ruleset matches the one committed here.

Branch protection is the one control in `docs/HARDENING.md` that lives outside
the repository: it is a setting on a server, changed by a click, invisible in
any diff. A checked-in JSON file describing what *should* be configured proves
nothing on its own — that is the same mistake as a status document claiming a
green run nobody produced.

So this reads the live configuration and compares.

    check_branch_protection.py --repo owner/name [--ruleset .github/rulesets/main.json]

Needs a token with `administration: read` in GITHUB_TOKEN (or --token). A
classic PAT needs `repo`; a fine-grained one needs Administration: Read-only.
The token this repository's CI holds is deliberately not that token, so this is
a maintainer tool run by hand, not a CI step.

Exit codes:
    0  live configuration satisfies every claim in the committed file
    1  drift: something claimed here is not true on the server
    2  could not tell (no token, network error, insufficient permission)

Exit 2 is not a pass. Being unable to read the configuration is indistinguishable
from the configuration being absent, and both are reported as unproven.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULESET = ROOT / ".github/rulesets/main.json"
API = "https://api.github.com"


class Unknown(Exception):
    """The live state could not be read. Never reported as a pass."""


def fetch(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gov-harness-check-branch-protection",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace").strip()
        if error.code in (401, 403):
            raise Unknown(
                f"{error.code} reading {url}: the token cannot read repository "
                f"administration. {detail}"
            ) from error
        if error.code == 404:
            raise Unknown(
                f"404 reading {url}: repository not found, or the token cannot "
                "see it."
            ) from error
        raise Unknown(f"{error.code} reading {url}: {detail}") from error
    except urllib.error.URLError as error:
        raise Unknown(f"cannot reach {url}: {error.reason}") from error


def rules_by_type(ruleset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["type"]: rule for rule in ruleset.get("rules", [])}


def compare_parameters(
    rule_type: str, want: dict[str, Any], live: dict[str, Any]
) -> list[str]:
    """Every parameter the committed file states must hold live.

    Only declared keys are compared. GitHub returns fields we never set, and
    demanding byte equality would turn a harmless API addition into a failure —
    a check that cries wolf gets switched off, and then it protects nothing.
    """
    findings: list[str] = []
    for key, expected in want.items():
        if key not in live:
            findings.append(f"{rule_type}.{key}: absent live, expected {expected!r}")
            continue
        actual = live[key]
        if key == "required_status_checks":
            want_checks = {(c["context"], c.get("integration_id")) for c in expected}
            live_checks = {(c["context"], c.get("integration_id")) for c in actual}
            for missing in sorted(want_checks - live_checks):
                findings.append(
                    f"{rule_type}: check {missing[0]!r} "
                    f"(integration {missing[1]}) is not required live"
                )
            continue
        if isinstance(expected, list) and isinstance(actual, list):
            if sorted(map(str, expected)) != sorted(map(str, actual)):
                findings.append(f"{rule_type}.{key}: live {actual!r}, want {expected!r}")
            continue
        if actual != expected:
            findings.append(f"{rule_type}.{key}: live {actual!r}, want {expected!r}")
    return findings


def compare(want: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Report every way the live ruleset falls short of the committed one."""
    findings: list[str] = []

    if live.get("enforcement") != want.get("enforcement", "active"):
        findings.append(
            f"enforcement: live {live.get('enforcement')!r}, "
            f"want {want.get('enforcement', 'active')!r} "
            "(an 'evaluate' ruleset reports violations and blocks nothing)"
        )

    if live.get("target") != want.get("target", "branch"):
        findings.append(f"target: live {live.get('target')!r}, want {want.get('target')!r}")

    want_refs = set(want.get("conditions", {}).get("ref_name", {}).get("include", []))
    live_refs = set(live.get("conditions", {}).get("ref_name", {}).get("include", []))
    for missing in sorted(want_refs - live_refs):
        findings.append(f"conditions: {missing} is not covered live")

    # An empty bypass list in the committed file is a claim, not a default: it
    # says nobody may push past these rules. A bypass actor added on the server
    # would leave every rule below technically "configured" and unenforced.
    if not want.get("bypass_actors"):
        live_bypass = live.get("bypass_actors") or []
        if live_bypass:
            names = ", ".join(
                f"{b.get('actor_type')}:{b.get('actor_id')}({b.get('bypass_mode')})"
                for b in live_bypass
            )
            findings.append(f"bypass_actors: live allows {names}, committed file allows none")

    want_rules = rules_by_type(want)
    live_rules = rules_by_type(live)
    for rule_type, want_rule in want_rules.items():
        if rule_type not in live_rules:
            findings.append(f"rule {rule_type!r}: absent live")
            continue
        findings.extend(
            compare_parameters(
                rule_type,
                want_rule.get("parameters", {}),
                live_rules[rule_type].get("parameters", {}) or {},
            )
        )
    return findings


def find_ruleset(owner: str, repo: str, name: str, token: str) -> dict[str, Any]:
    listing = fetch(f"{API}/repos/{owner}/{repo}/rulesets", token)
    for entry in listing:
        if entry.get("name") == name:
            # The listing omits rules; only the detail endpoint carries them.
            return fetch(
                f"{API}/repos/{owner}/{repo}/rulesets/{entry['id']}?includes_parents=false",
                token,
            )
    raise LookupError(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--ruleset", type=Path, default=DEFAULT_RULESET)
    parser.add_argument("--token", default=None, help="defaults to $GITHUB_TOKEN")
    args = parser.parse_args(argv)

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "UNKNOWN: no token. Set GITHUB_TOKEN to one with administration:read, "
            "or pass --token. Absence of a token is not a pass.",
            file=sys.stderr,
        )
        return 2

    if "/" not in args.repo:
        print(f"usage: --repo owner/name (got {args.repo!r})", file=sys.stderr)
        return 2
    owner, repo = args.repo.split("/", 1)

    try:
        want = json.loads(args.ruleset.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"UNKNOWN: cannot read {args.ruleset}: {error}", file=sys.stderr)
        return 2

    name = want.get("name")
    if not name:
        print(f"UNKNOWN: {args.ruleset} declares no ruleset name", file=sys.stderr)
        return 2

    try:
        live = find_ruleset(owner, repo, name, token)
    except Unknown as error:
        print(f"UNKNOWN: {error}", file=sys.stderr)
        return 2
    except LookupError:
        print(
            f"DRIFT: {args.repo} has no ruleset named {name!r}. "
            f"{args.ruleset} describes protection that does not exist.",
            file=sys.stderr,
        )
        return 1

    findings = compare(want, live)
    if findings:
        print(f"DRIFT: {args.repo} ruleset {name!r} does not match {args.ruleset}", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding}", file=sys.stderr)
        return 1

    checks = ", ".join(
        c["context"]
        for c in rules_by_type(want)
        .get("required_status_checks", {})
        .get("parameters", {})
        .get("required_status_checks", [])
    )
    print(
        f"{args.repo}: ruleset {name!r} active on "
        f"{', '.join(want['conditions']['ref_name']['include'])}"
        + (f", required checks: {checks}" if checks else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
