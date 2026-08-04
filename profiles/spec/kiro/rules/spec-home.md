---
id: governance/rules/spec-home
class: state
status: active
owner: governance-harness
updated: 2026-08-04
sources: [profiles/spec/kiro/rules/spec-home.md]
---

# Specification Home — Kiro

This repository keeps present-tense requirement truth under `.kiro/specs/`.
This rule binds the neutral SDD lifecycle to that layout. It replaces no phase
and waives no gate.

## Prerequisite

`.kiro/specs/` must already be the repository's adopted convention. Select this
binding only when the target explicitly adopts Kiro; do not create the tree
merely because this profile is installed. If the repository has no adopted
layout, select the `spec/plain` binding instead.

## Truth layout

```text
.kiro/specs/<feature>/requirements.md   requirements    class: state
.kiro/specs/<feature>/design.md         design          class: state
.kiro/specs/<feature>/tasks.md          task list       class: event
.kiro/steering/product.md               steering        class: state
.kiro/steering/tech.md                  steering        class: state
.kiro/steering/structure.md             steering        class: state
```

Feature documents describe the capability. When run evidence is captured
separately, store it outside the spec tree: a spec describes what the system
does, a run describes one execution of a change.

## Precedence

`.kiro/specs/` is the home only while no stronger home exists.

- If `openspec/` exists in this repository, it wins. Stop with
  `spec_home_conflict` and report both paths rather than writing into
  `.kiro/specs/`.
- Never create `requirements/` or `spec/` beside `.kiro/specs/`.
- Never demote the home because a ticket, planner classification, label or
  compaction summary suggests another layout.

## Requirement shape

The EARS rule stays authoritative for the logic of an acceptance criterion.
This binding fixes only its placement: acceptance criteria live in
`requirements.md` under a requirement heading carrying a stable canonical ID,
and the same ID is what design, tasks and verification reference. Never
renumber an existing requirement to fit a template.

Design traceability, task-to-requirement mapping and coverage remain governed
by the design review gate and the tasks generation rule.

## Validation

Kiro ships no structural validator for these documents. The mechanical checks
in the requirements and design review gates are therefore performed by the
agent, and their result is reviewer-verified rather than tool-verified. Say so
when reporting a phase gate: this binding is a tier-2 discipline, not a
tier-3 parser. Do not present a self-check as machine evidence.

## Mapping to governance lifecycle

| Governance concept | Kiro artifact |
|---|---|
| present-tense state | `.kiro/specs/<feature>/requirements.md`, `design.md` |
| change event | `.kiro/specs/<feature>/tasks.md` |
| seal | repository convention; none is provided by the tool |
| structured requirement check | none — reviewer judgment only |
| absorbed local document | frontmatter `superseded_by:` naming the spec path |

The authoring rules name artifact roles, not files. In this binding they
resolve as follows:

| Role | Resolves to |
|---|---|
| `requirements.md` | `.kiro/specs/<feature>/requirements.md` |
| `design.md` | `.kiro/specs/<feature>/design.md` |
| `tasks.md` | `.kiro/specs/<feature>/tasks.md` |
| `research.md` | `.kiro/specs/<feature>/research.md` when the repository keeps one; otherwise a clearly separated section of the design artifact |
