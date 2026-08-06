#!/usr/bin/env python3
"""Guard release contents that rot silently when something else changes."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))
FILES = MANIFEST["files"]
POLICIES = ROOT / "core/policies"
SPEC_HOME_DESTINATION = "docs/governance/rules/spec-home.md"


def destinations(**match: object) -> list[dict[str, object]]:
    return [
        item
        for item in FILES
        if all(item.get(key) == value for key, value in match.items())
    ]


class PolicyExampleTests(unittest.TestCase):
    """The gates default to project-owned config; the examples must stay usable."""

    def examples(self) -> dict[str, dict[str, object]]:
        return {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in POLICIES.glob("*.example.json")
        }

    def test_every_example_is_shipped(self) -> None:
        shipped = {
            str(item["destination"]) for item in FILES if "policy.example.json" in str(item["destination"])
        }
        self.assertEqual(
            {f"docs/governance/{name}" for name in self.examples()},
            shipped,
        )

    def test_every_example_parses_with_the_expected_schema(self) -> None:
        examples = self.examples()
        self.assertEqual(3, len(examples), sorted(examples))
        for name, value in sorted(examples.items()):
            with self.subTest(policy=name):
                self.assertEqual(1, value.get("schema_version"))
                self.assertIsInstance(value.get("_about"), list)

    def test_docs_example_configures_the_spec_home_gate(self) -> None:
        docs = self.examples()["docs-policy.example.json"]
        self.assertIn("spec_homes", docs)
        self.assertIn("spec_home", docs)
        self.assertIn("openspec/specs", docs["spec_homes"])
        # Undeclared by default: an example must not assert a home for a
        # repository it has never seen.
        self.assertIsNone(docs["spec_home"])

    def test_skill_example_declares_no_receipt_owned_skills(self) -> None:
        """SKILL-G reads those from the lock; restating them is what rots."""
        listed = self.examples()["skill-policy.example.json"]["skills"]
        self.assertEqual({}, listed)

    def test_skill_example_lists_every_target_root(self) -> None:
        listed = self.examples()["skill-policy.example.json"]["skills_root"]
        self.assertEqual([target["root"] for target in MANIFEST["targets"]], listed)


class SpecHomeFamilyTests(unittest.TestCase):
    def test_every_variant_shares_the_canonical_destination(self) -> None:
        variants = destinations(destination=SPEC_HOME_DESTINATION)
        self.assertEqual(
            {"spec/kiro", "spec/openspec", "spec/plain"},
            {str(item["profile"]) for item in variants},
        )
        for item in variants:
            with self.subTest(profile=item["profile"]):
                self.assertEqual("profile", item["layer"])

    def test_every_spec_profile_is_described_in_the_menu(self) -> None:
        described = {entry["name"] for entry in MANIFEST["profile_info"]}
        self.assertLessEqual(
            {"spec/kiro", "spec/openspec", "spec/plain"}, described
        )

    def test_core_ships_no_specification_layout(self) -> None:
        """ADR-0008: the spine names no tool and no path layout."""
        forbidden = (".kiro/", "openspec/", "cc-sdd")
        for item in destinations(layer="core"):
            source = ROOT / str(item["source"])
            if source.suffix != ".md":
                continue
            text = source.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(source=item["source"], marker=marker):
                    self.assertNotIn(marker, text)


class ProfileGateTests(unittest.TestCase):
    def test_the_adr_profile_ships_the_gate_its_skill_names(self) -> None:
        gates = destinations(profile="adr", destination="scripts/verify-adr.py")
        self.assertEqual(1, len(gates))
        self.assertTrue(gates[0]["executable"])
        skill = (ROOT / "profiles/adr/skills/adr/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("scripts/verify-adr.py", skill)
        self.assertNotIn("verify-requirements.sh", skill)


if __name__ == "__main__":
    unittest.main()
