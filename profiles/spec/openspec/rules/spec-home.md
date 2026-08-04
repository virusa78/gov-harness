---
id: governance/rules/spec-home
class: state
status: active
owner: governance-harness
updated: 2026-08-04
sources: [profiles/spec/openspec/rules/spec-home.md]
---

# Specification Home — OpenSpec

This repository keeps present-tense requirement truth in OpenSpec. This rule
binds the neutral SDD lifecycle to that tool: where truth lives, what a
requirement looks like, and which command decides whether it is well formed.
It replaces no phase and waives no gate.

## Prerequisite

OpenSpec is a global CLI. The harness cannot install it and must not pretend
it is optional.

```bash
npm install -g @fission-ai/openspec@latest   # or: pnpm add -g / bun add -g
openspec init                                 # inside the target repository
```

Node.js 20.19.0 or higher is required. `openspec init` generates six base
capabilities — **propose, explore, apply, update, sync, archive** — invoked as
`/opsx-*` or `/openspec-*` depending on the agent tool. Installation order is
prescribed by the upstream documentation:
<https://github.com/Fission-AI/OpenSpec/blob/main/docs/installation.md>.

If `openspec/` is absent and the CLI is not installed, report a prerequisite
gap and stop. Do not silently fall back to another layout, and do not create a
substitute tree by hand. A missing tool is a gap, not a licence to invent one.

## Truth layout

```text
openspec/specs/<capability>/spec.md   current truth       class: state
openspec/changes/<id>/proposal.md     why and what         class: event
openspec/changes/<id>/design.md       technical approach   class: event
openspec/changes/<id>/tasks.md        implementation list  class: event
openspec/changes/<id>/specs/...       requirement deltas   class: event
openspec/changes/archive/             sealed changes       class: event, sealed
```

`openspec/specs/` speaks in the present tense; a change speaks about a
transition. `openspec archive` is the seal: after it runs, the change is a
finished event and its deltas have become current truth. Do not edit an
archived change to restate today's behavior — amend the spec instead.

## Precedence

When `openspec/` exists in the target repository it **is** the specification
home. In that case:

- never create `requirements/`, `.kiro/specs/` or `spec/` beside it;
- never demote it because a ticket, planner classification, label or
  compaction summary suggests another layout;
- if another home already holds content, stop with `spec_home_conflict` and
  report both paths. Migrating truth is a reviewed change, not a side effect.

A different selected binding does not override a present `openspec/`; it means
the selection and the repository disagree, which is the same conflict.

## Requirement and scenario shape

The EARS rule stays authoritative for the *logic* of an acceptance criterion —
condition, subject, mandatory response. This binding fixes only its *form*:

```markdown
## ADDED Requirements

### Requirement: <short capability statement>
The <system> SHALL <observable behavior>.

#### Scenario: <short case name>
- **WHEN** <trigger>
- **THEN** <observable outcome>
```

Delta headers in a change are `## ADDED Requirements`,
`## MODIFIED Requirements`, `## REMOVED Requirements` and
`## RENAMED Requirements`. A `MODIFIED` entry carries the complete requirement
block, not just the changed line; a partial block loses the context a reviewer
needs and the validator rejects it.

Every requirement carries at least one scenario. A requirement without a
scenario has no acceptance criterion, which the requirements review gate
already forbids in prose and the validator now refuses mechanically.

Requirement identity is the heading text. Preserve canonical source IDs from
the originating ticket or specification inside the requirement body, and keep
one repository convention for new ones.

## Validation is a gate, not a habit

```bash
openspec validate --all --strict
```

Run it before claiming any phase complete. `--strict` promotes warnings to
failures; it catches a requirement with no scenario, a malformed scenario
heading, and a `MODIFIED` delta missing its full block. Treat a non-zero exit
as a failed phase gate.

This is a structural validator, not a semantic one. It proves the shape of a
requirement, never its truth. Reviewer judgment under the requirements and
design review gates remains mandatory — never report a green validator as
evidence that the behavior is correct.

## Mapping to governance lifecycle

| Governance concept | OpenSpec artifact |
|---|---|
| present-tense state | `openspec/specs/<capability>/spec.md` |
| change event | `openspec/changes/<id>/` |
| seal | `openspec archive <id>` |
| structured requirement check | `openspec validate --strict` |
| absorbed local document | frontmatter `superseded_by:` naming the spec path |

The authoring rules name artifact roles, not files. In this binding they
resolve as follows:

| Role | Resolves to |
|---|---|
| `requirements.md` | `openspec/specs/<capability>/spec.md`, and the requirement deltas under `openspec/changes/<id>/specs/` while a change is in flight |
| `design.md` | `openspec/changes/<id>/design.md` |
| `tasks.md` | `openspec/changes/<id>/tasks.md` |
| `research.md` | `openspec/changes/<id>/design.md`, investigation sections; OpenSpec ships no separate research artifact |

Because research has no artifact of its own here, rules that push investigation
detail out of design have nowhere to push it. Keep the detail in the design
artifact under a clearly separated section rather than creating a parallel file
outside the home.

A governance document whose content has moved into OpenSpec is not deleted
silently and not left to rot in the present tense. Set `status: superseded`
and name the owning spec file in `superseded_by:`. Prose reassurance that
"this now lives in OpenSpec" is not a record.
