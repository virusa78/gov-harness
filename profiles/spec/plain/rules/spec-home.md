---
id: governance/rules/spec-home
class: state
status: active
owner: governance-harness
updated: 2026-08-04
sources: [profiles/spec/plain/rules/spec-home.md]
---

# Specification Home — Plain Markdown

This repository keeps present-tense requirement truth in a plain `requirements/`
tree with no specification tool behind it. This rule binds the neutral SDD
lifecycle to that layout. It replaces no phase and waives no gate.

## Prerequisite

None. This binding is the fallback for repositories that have not adopted a
specification tool. It is the weakest of the three: every mechanical check is
performed by the agent and confirmed by a reviewer, with no parser in the loop.
Prefer a tool-backed binding when the repository can adopt one.

## Truth layout

```text
requirements/<feature>.discovery.md      discovery      class: state
requirements/<feature>.requirements.md   requirements   class: state
requirements/<feature>.research.md       research       class: state
requirements/<feature>.design.md         design         class: state
requirements/<feature>.tasks.md          task list      class: event
requirements/<feature>.verification.md   verification   class: event
```

Feature documents describe the capability. When run evidence is captured
separately, store it outside `requirements/`: a feature document describes what
the system does, a run document describes one execution.

## Precedence

`requirements/` is the home only while no stronger home exists.

- If `openspec/` exists in this repository, it wins. Stop with
  `spec_home_conflict` and report both paths rather than writing into
  `requirements/`.
- If `.kiro/specs/` already holds content, stop with the same conflict rather
  than opening a second home.
- Never demote the home because a ticket, planner classification, label or
  compaction summary suggests another layout.

## Requirement shape

The EARS rule stays authoritative for the logic of an acceptance criterion.
This binding fixes only its placement: acceptance criteria live in
`<feature>.requirements.md` under a requirement heading carrying a stable
canonical ID, and the same ID is what design, tasks and verification
reference. Never renumber an existing requirement to fit a template.

## Validation

There is no structural validator. The mechanical checks listed in the
requirements and design review gates are performed by the agent and confirmed
by a reviewer. Report the phase gate honestly: this is tier-2 discipline, and
a self-check is never machine evidence.

Where the repository owns an executable requirements checker, run it and name
it in the phase gate. Its path is a local environment fact; this rule never
assumes one exists.

## Mapping to governance lifecycle

| Governance concept | Plain artifact |
|---|---|
| present-tense state | `requirements/<feature>.requirements.md`, `.design.md` |
| change event | `requirements/<feature>.tasks.md`, `.verification.md` |
| seal | repository convention; none is provided by a tool |
| structured requirement check | none — reviewer judgment only |
| absorbed local document | frontmatter `superseded_by:` naming the owning file |

The authoring rules name artifact roles, not files. In this binding they
resolve as follows:

| Role | Resolves to |
|---|---|
| `requirements.md` | `requirements/<feature>.requirements.md` |
| `design.md` | `requirements/<feature>.design.md` |
| `tasks.md` | `requirements/<feature>.tasks.md` |
| `research.md` | `requirements/<feature>.research.md` |
