#!/usr/bin/env python3
"""The branch-protection checker must catch the ways protection quietly lapses.

Every case below is a real configuration that leaves the ruleset present and
looking configured while enforcing nothing. A checker that passes them is worse
than no checker: it converts an unprotected branch into a green line.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULESET = ROOT / ".github/rulesets/main.json"
CHECKER = ROOT / "scripts/check_branch_protection.py"
sys.path.insert(0, str(ROOT / "scripts"))
import check_branch_protection as cbp  # noqa: E402


def committed() -> dict:
    return json.loads(RULESET.read_text(encoding="utf-8"))


def live_from(want: dict) -> dict:
    """What GitHub would return if the committed file were applied verbatim."""
    live = copy.deepcopy(want)
    # Fields the API adds and we never set. The checker must ignore them.
    live["id"] = 1234
    live["source"] = "virusa78/gov-harness"
    live["source_type"] = "Repository"
    live["node_id"] = "RRS_lACo"
    live["created_at"] = "2026-08-07T07:00:00Z"
    return live


class CommittedRulesetTests(unittest.TestCase):
    def test_it_is_valid_json_and_names_itself(self) -> None:
        self.assertTrue(committed()["name"])

    def test_it_claims_active_enforcement(self) -> None:
        """'evaluate' reports violations and blocks nothing."""
        self.assertEqual("active", committed()["enforcement"])

    def test_it_covers_the_default_branch(self) -> None:
        self.assertIn("~DEFAULT_BRANCH", committed()["conditions"]["ref_name"]["include"])

    def test_it_allows_no_bypass(self) -> None:
        self.assertEqual([], committed()["bypass_actors"])

    def test_it_requires_the_check_ci_actually_publishes(self) -> None:
        """The context must be the job name in ci.yml, or nothing is required."""
        checks = cbp.rules_by_type(committed())["required_status_checks"]["parameters"][
            "required_status_checks"
        ]
        contexts = {c["context"] for c in checks}
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for context in contexts:
            with self.subTest(context=context):
                self.assertIn(f"  {context}:", workflow)

    def test_it_pins_the_check_to_github_actions(self) -> None:
        """Without integration_id any app could satisfy the requirement."""
        checks = cbp.rules_by_type(committed())["required_status_checks"]["parameters"][
            "required_status_checks"
        ]
        for check in checks:
            with self.subTest(context=check["context"]):
                self.assertEqual(15368, check["integration_id"])

    def test_it_blocks_deletion_and_force_push(self) -> None:
        types = set(cbp.rules_by_type(committed()))
        self.assertIn("deletion", types)
        self.assertIn("non_fast_forward", types)


class ComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.want = committed()

    def test_an_exact_match_reports_nothing(self) -> None:
        self.assertEqual([], cbp.compare(self.want, live_from(self.want)))

    def test_extra_api_fields_are_not_drift(self) -> None:
        live = live_from(self.want)
        live["rules"][0]["some_future_field"] = "added by GitHub"
        self.assertEqual([], cbp.compare(self.want, live))

    def test_evaluate_mode_is_drift(self) -> None:
        live = live_from(self.want)
        live["enforcement"] = "evaluate"
        self.assertTrue(any("enforcement" in f for f in cbp.compare(self.want, live)))

    def test_a_bypass_actor_is_drift(self) -> None:
        live = live_from(self.want)
        live["bypass_actors"] = [
            {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
        ]
        findings = cbp.compare(self.want, live)
        self.assertTrue(any("bypass_actors" in f for f in findings), findings)

    def test_a_dropped_rule_is_drift(self) -> None:
        live = live_from(self.want)
        live["rules"] = [r for r in live["rules"] if r["type"] != "required_status_checks"]
        findings = cbp.compare(self.want, live)
        self.assertTrue(any("required_status_checks" in f for f in findings), findings)

    def test_a_dropped_required_check_is_drift(self) -> None:
        live = live_from(self.want)
        for rule in live["rules"]:
            if rule["type"] == "required_status_checks":
                rule["parameters"]["required_status_checks"] = []
        findings = cbp.compare(self.want, live)
        self.assertTrue(any("verify" in f for f in findings), findings)

    def test_a_check_claimed_by_another_app_is_drift(self) -> None:
        """Same context name, different app, is a different check."""
        live = live_from(self.want)
        for rule in live["rules"]:
            if rule["type"] == "required_status_checks":
                for check in rule["parameters"]["required_status_checks"]:
                    check["integration_id"] = 99999
        findings = cbp.compare(self.want, live)
        self.assertTrue(any("verify" in f for f in findings), findings)

    def test_losing_strict_mode_is_drift(self) -> None:
        """Non-strict lets a PR merge green against a base it never saw."""
        live = live_from(self.want)
        for rule in live["rules"]:
            if rule["type"] == "required_status_checks":
                rule["parameters"]["strict_required_status_checks_policy"] = False
        findings = cbp.compare(self.want, live)
        self.assertTrue(any("strict" in f for f in findings), findings)

    def test_narrowing_the_ref_condition_is_drift(self) -> None:
        live = live_from(self.want)
        live["conditions"]["ref_name"]["include"] = ["refs/heads/nothing"]
        findings = cbp.compare(self.want, live)
        self.assertTrue(any("DEFAULT_BRANCH" in f for f in findings), findings)


class FailClosedTests(unittest.TestCase):
    def run_checker(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        import os

        environment = dict(os.environ)
        environment.pop("GITHUB_TOKEN", None)
        environment.pop("GH_TOKEN", None)
        if env:
            environment.update(env)
        return subprocess.run(
            [sys.executable, str(CHECKER), *args],
            check=False, capture_output=True, text=True, env=environment,
        )

    def test_no_token_is_unknown_not_pass(self) -> None:
        done = self.run_checker("--repo", "virusa78/gov-harness")
        self.assertEqual(2, done.returncode)
        self.assertIn("not a pass", done.stderr)

    def test_a_missing_ruleset_file_is_unknown(self) -> None:
        done = self.run_checker(
            "--repo", "virusa78/gov-harness",
            "--ruleset", str(ROOT / "does-not-exist.json"),
            env={"GITHUB_TOKEN": "unused"},
        )
        self.assertEqual(2, done.returncode)
        self.assertIn("UNKNOWN", done.stderr)

    def test_a_malformed_repo_argument_is_rejected(self) -> None:
        done = self.run_checker("--repo", "gov-harness", env={"GITHUB_TOKEN": "unused"})
        self.assertEqual(2, done.returncode)


if __name__ == "__main__":
    unittest.main()
