---
id: governance/rules/bdd-format
class: state
status: active
owner: governance-harness
updated: 2026-07-29
sources: [core/rules/bdd-format.md]
---

# BDD Format Guidelines

## Overview

BDD (Behaviour-Driven Development) is the **executable acceptance layer** of the
gate-based workflow. It sits between EARS requirements (WHAT must be true) and the
verification gate (PROOF it is true):

```
SDD (phases) → EARS (requirements) → BDD (scenarios) → Gate (executable proof)
```

Where an EARS requirement states a rule, a BDD scenario states an **observable
example** of that rule holding — concrete inputs, a concrete action, and a
concrete, checkable outcome. A scenario is the specification a gate step executes.

BDD does **not** replace EARS. EARS remains the normative source of truth; every
scenario **traces back** to one or more EARS IDs. BDD makes those requirements
runnable and gives the deploy gate its checklist.

## File placement

- One feature file per SDD feature: `requirements/{feature}.feature`.
- Slug matches the SDD document set (`{feature}.requirements.md` ↔ `{feature}.feature`).
- Plain Gherkin. No framework-specific glue in the `.feature` file itself.

## Gherkin structure

```gherkin
Feature: <short capability name>
  <one-paragraph business intent, mirrors the requirements-doc scope>

  Background:
    Given <preconditions shared by every scenario below>

  @<EARS-ID>
  Scenario: <one observable behaviour, named for the outcome>
    Given <deterministic starting state>
    When  <single action under test>
    Then  <a checkable outcome — status code, row, latency, topic>
    And   <further checkable outcomes>
```

- **Feature** — the capability. Mirrors the `.requirements.md` scope line.
- **Background** — preconditions true for all scenarios (stack up, seed applied,
  clean outbox/inbox). Never put an assertion or an irreversible mutation in
  Background; scenario order must not affect the result. Any setup performed
  there must be idempotent.
- **Scenario** — exactly **one** behaviour with a single `When`. If you need two
  actions to reach the outcome, the first is a `Given`.
- **Scenario Outline / Examples** — use for the *same* behaviour across a data
  set (e.g. CRUD across every service, one row per endpoint). Keeps N services
  from becoming N copy-pasted scenarios.

## Traceability (mandatory)

- Every `Scenario`/`Scenario Outline` carries a tag naming the EARS ID(s) it
  verifies: `@INV-U2`, `@E2E-U1`. A scenario may carry several tags when it
  exercises several requirements in one flow.
- **Coverage rule**: every EARS requirement that is in the deploy gate
  (`requires_gate`) MUST have at least one tagged scenario. A gate-required EARS
  ID with no scenario is a coverage gap and fails the BDD review gate.
- The reverse also holds: a scenario with no `@EARS-ID` tag is orphaned — either
  tag it or delete it. No untraceable scenarios.

## Step-writing rules

1. **Observable, not internal.** Steps assert things a gate can see from outside:
   HTTP status, a response field, a DB row, a broker message, a measured latency.
   Never "the service correctly processes" — say *what is observably true after*.
2. **Concrete anchors.** Use the real endpoint, topic, status code, table, and
   SLA from the design doc — not paraphrase. `Then the response status is 403`,
   not "then it is rejected".
3. **Deterministic data.** Fixed tenant IDs, fixed seed rows, fixed idempotency
   keys. Same starting state ⇒ same result (the gate must be repeatable).
4. **One outcome family per scenario.** Happy path and each failure mode
   (403, 400, timeout, duplicate) are *separate* scenarios, separately tagged.
5. **Declarative, not imperative.** Say the intent ("When the order is executed"),
   not UI mechanics. The step definition owns the HOW.
6. **Latency/SLA is a `Then`.** If the requirement has an SLA, assert it:
   `Then the projection is visible within 5 seconds`.

## Mapping EARS patterns → Gherkin

| EARS pattern | Gherkin shape |
|---|---|
| Ubiquitous — "The system shall X" | `Given` normal state · `When` action · `Then` X holds |
| Event — "When E, the system shall R" | `When` E · `Then` R |
| Unwanted — "If T, then shall R" | `Given` the T condition · `When` action · `Then` R (the guard fires) |
| State — "While P, the system shall R" | `Given` P holds · `When` action · `Then` R |

An EARS requirement with both a happy clause and an `IF … THEN` failure clause
becomes **two** scenarios (one per branch), each tagged with the same EARS ID.

## BDD Review Gate (run before wiring scenarios into a gate script)

- [ ] Every `requires_gate` EARS ID has ≥1 tagged scenario (coverage complete).
- [ ] Every scenario is tagged with a real EARS ID (no orphans).
- [ ] Each scenario has exactly one `When`; failure modes are separate scenarios.
- [ ] Every `Then` is externally observable (status/row/message/latency).
- [ ] Data is deterministic (fixed tenant/keys/seed) — repeatable.
- [ ] Anchors (endpoints, topics, SLAs) match the design doc, not paraphrase.

Record pass/fail in the feature's `.requirements.md` Verification Log
(`BDD Review | PASS/FAIL`).

## Relationship to the gate script

The `.feature` file is the human- and machine-readable contract; the gate script
(`scripts/verify-*.sh` / test suite) is its execution. Each scenario maps to one
gate step, and the step reports PASS/FAIL under the scenario's EARS tag, so a red
gate names the exact requirement that regressed.
