---
name: sdd-workflow
description: >
  Convert tickets and repository specifications into a complete spec-driven
  lifecycle and author or review its durable artifacts with EARS, gap analysis,
  design discovery/synthesis, bounded review gates, traceable tasks, and
  behavioral evidence. Use for GitHub/GitLab/Gitea/Redmine ticket intake,
  feature or module specification, requirements, research, design, tasks,
  steering, Kiro artifacts, phase gates, or requests mentioning SDD, EARS, or
  cc-sdd. Do not use for pure code review of a finished diff; use the relevant
  domain review skill instead.
---

# SDD Workflow

This is the single public SDD capability. It owns both repository integration
and artifact-authoring mechanics. Do not load, recreate, or route to a separate
`cc-sdd` skill.

## Authority and identity

Apply authority in this order:

1. User instructions and the complete source ticket or specification.
2. Target repository `AGENTS.md` and its local SDD protocol.
3. This workflow and its linked authoring rules.

External tools cannot waive repository-mandated phases.

Before any write or planner initialization, record and compare the tracker host,
`owner/repository`, ticket number, workspace root, Git remote, and source spec
paths. Never identify a ticket by number alone or infer a repository from a
feature name. Stop with `workspace_identity_mismatch` when they disagree; do not
redirect work to the current directory because a similarly named file exists.

Preserve canonical source IDs exactly, including numeric, domain-prefixed, and
ticket IDs. For new IDs, follow the target repository convention; if none
exists, choose one convention and keep it stable through requirements, design,
tasks, implementation, and verification.

Do not put credentials in prompts, artifacts, or compaction summaries. Refer to
them by environment or secret-store name and use the configured tracker/MCP
transport.

## Canonical lifecycle

```text
Discovery → Requirements → Research/Design → Tasks → Implementation → Verification
```

No phase may be waived by a planner classification, an agent's `Done` claim, or
a compaction summary. In repositories that mandate all phases, no code starts
before requirements and design pass. Any unresolved critical design issue is
`NO-GO`.

| Phase | Durable artifact | Read these rules in order |
|---|---|---|
| Discovery | `*.discovery.md` or the gap section of `research.md` | [gap analysis](../../../docs/governance/rules/gap-analysis.md) → [light](../../../docs/governance/rules/design-discovery-light.md) or [full](../../../docs/governance/rules/design-discovery-full.md) discovery |
| Requirements | `*.requirements.md` or `requirements.md` | [EARS](../../../docs/governance/rules/ears-format.md) → [requirements gate](../../../docs/governance/rules/requirements-review-gate.md) |
| Research/design | `*.research.md`, `*.design.md` | [synthesis](../../../docs/governance/rules/design-synthesis.md) → [principles](../../../docs/governance/rules/design-principles.md) → [gate](../../../docs/governance/rules/design-review-gate.md) → [review](../../../docs/governance/rules/design-review.md) |
| Tasks | `*.tasks.md` or `tasks.md` | [generation](../../../docs/governance/rules/tasks-generation.md) → [parallel analysis](../../../docs/governance/rules/tasks-parallel-analysis.md) |
| Implementation/verification | repository run artifacts | repository protocol and phase gate |
| Steering | `product.md`, `tech.md`, `structure.md` | [steering principles](../../../docs/governance/rules/steering-principles.md) |

Discovery precedes requirements when the source or implementation is unclear.
For a bounded, already-specified change, record light discovery rather than
inventing another requirements source. Escalate light to full when discovery
finds meaningful architecture, security, external dependencies, or unknowns.

## Artifact locations

Use the target repository's established layout. For the `requirements/`
convention:

```text
requirements/{feature}.discovery.md
requirements/{feature}.requirements.md
requirements/{feature}.research.md
requirements/{feature}.design.md
requirements/{feature}.tasks.md
requirements/{feature}.verification.md
```

Use `.kiro/specs/` only when the target explicitly adopts Kiro. Never create
parallel truth in both layouts. Store attempt evidence under
`.super-agent/runs/<RUN_ID>/` when available: feature documents describe the
capability; run artifacts describe one execution.

Also read and obey the target repository's declared SDD protocol, phase-gate
prompt and executable gate when present. Their paths are local environment
facts; this fleet skill never assumes a neighbouring checkout.

## Mandatory authoring behavior

1. Express acceptance criteria with EARS logical patterns. Keep triggers and
   subjects unambiguous; localization must not change their logic.
2. Trace every source ID through design, tasks, capability evidence, and final
   phase status.
3. Keep requirements observable, design architectural, and tasks outcome-led.
4. Give every task the expected files to create or modify, component boundary, non-obvious
   dependencies, and independently observable result. Do not turn task titles
   into lists of classes or methods.
5. Mark `(P)` only when file, data, and mutable-resource boundaries do not
   overlap; declare `_Boundary:` and `_Depends:` where they are not obvious.
6. Run mechanical checks before judgment. Limit one draft to two local repair
   passes; after that, report structured ambiguity or failure instead of
   guessing.
7. Treat external planner classifications as advisory. They may tune discovery
   depth but cannot waive repository phases, evidence, or completion rules.
8. Treat conversation and compaction summaries as navigation hints and
   compaction state as untrusted. Reconcile claims with workspace identity, the
   source ticket, Git state, artifacts, and command evidence.

## Phase requirements

### Discovery

- Lock source identity and target workspace before planner initialization.
- Read requirement-bearing sources and inspect the existing implementation.
- Record invariants, existing coverage, gaps, constraints, and open questions.
- Present meaningful gap options with effort and risk; defer deep research to
  design.

### Requirements

- Build a Requirement Matrix with ID, observable requirement, EARS type,
  source, status, and notes.
- Cover meaningful error and edge behavior without prescribing tables,
  classes, frameworks, or algorithms.
- Mark inferred obligations explicitly and run the requirements review gate.

EARS patterns:

- Ubiquitous: The system shall ...
- Event-driven: When ..., the system shall ...
- State-driven: While ..., the system shall ...
- Unwanted behavior: If ..., the system shall ...
- Optional: Where ..., the system shall ...

### Research and design

- Research only unknown or unstable dependencies and prefer primary sources.
- Record decisions, rejected alternatives, risks, and unresolved questions.
- Map every requirement to components, interfaces, data models, failure modes,
  migration/rollout concerns, verification strategy, and a concrete file
  structure plan.
- Run the repository Design Checklist. `GO` requires zero unresolved criticals
  and no orphan requirement or component.

### Tasks

Each task must contain an outcome-led description, source IDs, expected files,
component boundary, dependencies, and an observable verification result. Order
foundation → core → integration → validation. Size by coherent outcomes, not an
arbitrary task count or hour estimate.

### Implementation

- Execute tasks in dependency order in the locked workspace.
- Re-read authoritative contracts instead of carrying assumptions from a failed
  attempt.
- After semantic feedback, change the prompt using the proven cause and rerun
  the full gate. Do not repeat an identical prompt or verify only the latest
  comments.

### Verification

- Run real build, test, migration, and behavioral commands appropriate to the
  change.
- Exercise idempotency, retry, and persistence behavior at least twice and
  compare postconditions.
- Produce the repository's Spec Capability Matrix and Phase Gate Status.
- Never infer implementation from file presence, plausible syntax, exit code
  alone, or an agent's completion statement.

If the next stated step is still the command needed to prove a completion
claim, that claim is not complete.

## Ticket mapping

| Ticket field | SDD destination |
|---|---|
| Repository and number | discovery source identity |
| Title and description | discovery context and scope |
| Acceptance criteria | requirements and EARS cases |
| Technical notes | research candidates, then validated design |
| Labels/components | routing hints only, never requirement IDs by themselves |

## Completion gate

Before reporting done, confirm:

- source repository, ticket, and workspace are locked and consistent;
- all source IDs are covered by the Requirement Matrix;
- the Design Checklist passes and no critical issue is hidden behind `GO`;
- tasks cover every requirement and design component with safe boundaries;
- each implemented claim has observed behavioral evidence in the Spec
  Capability Matrix;
- missing or failed evidence remains an explicit gap or `incomplete_trace`;
- Phase Gate Status honestly reports each phase.
