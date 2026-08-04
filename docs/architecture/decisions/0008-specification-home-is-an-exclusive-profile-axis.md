# ADR-0008: The specification home is an exclusive profile axis

## Status

Accepted — 2026-08-04. This ADR records the decision; the release behavior it
describes is not built yet (see Implementation status).

## Context

`core/` ships two incompatible models of where truth lives, and neither
references the other:

- `core/skills/sdd-workflow/SKILL.md` places truth in
  `requirements/{feature}.*.md` or `.kiro/specs/`, and forbids parallel truth
  "in both layouts";
- `core/skills/truth-pipeline/SKILL.md` places truth in `spec/` (state) and
  `tasks/` (sealed events), under the heading "Two document types (there are
  no others)".

A consumer that installs both receives two documents each claiming to be the
single home of truth. That is precisely the fork `truth-pipeline` rule 1
forbids. All thirteen `core/rules/` files are written against the first model
only, so the second arrives without the rules that would govern it.

OpenSpec is absent from the release entirely. Structurally it is the same
model as `truth-pipeline` with a parser behind it: `openspec/specs/` holds
current state, `openspec/changes/<id>/` holds a change event, `openspec
archive` seals it into the specs, and `openspec validate --strict` enforces
`### Requirement:` and `#### Scenario:` shape — including "a requirement with
no scenario" and "a MODIFIED delta missing its full requirement block". In
`truth-pipeline`'s own tier taxonomy that is a tier-3 structured spec, while
this release offers tier 1 as prose and asks a reviewer to check the rest by
eye.

ADR-0007 moved stack content out of `core/` because a Kafka rule installed
into a NATS repository stated things that were false there. The same defect
stands unaddressed on the specification-tool axis: `sdd-workflow` names Kiro
and cc-sdd and prescribes a path layout, so in a repository whose truth lives
in `openspec/` a core skill instructs the agent to build a second head of
truth. Neutrality was again a review convention rather than a property of the
release format.

Finally, OpenSpec is a prerequisite this harness cannot install for a
consumer. Its documented order is a global package
(`npm install -g @fission-ai/openspec@latest`, Node.js 20.19.0 or higher),
then `openspec init` inside the project, which generates six base
capabilities — propose, explore, apply, update, sync, archive — invoked as
`/opsx-*` or `/openspec-*` depending on the agent tool. The release names none
of this, so a consumer cannot tell what must already exist before the doctrine
applies, and an agent cannot tell whether the absence of `openspec/` means
"not adopted" or "not installed yet".

## Decision

1. **One specification home per repository.** A repository has exactly one
   directory tree that holds present-tense requirement truth. Every other
   governance document either references it or declares, in frontmatter, that
   its content was absorbed into it. Prose reassurance does not count.

2. **`core/` keeps only the neutral spine.** The phase lifecycle, EARS logical
   patterns, review gates, traceability obligations and completion rules stay
   in `core/` and name no tool and no path layout. The spine must be true in
   every consumer regardless of which specification tool it runs.

3. **`spec/` becomes a profile family.** Variants `spec/openspec`,
   `spec/kiro` and `spec/plain` are mutually exclusive under the ADR-0007
   family mechanism and share the canonical destination, so selecting a
   variant swaps the binding in place. A variant supplies only the binding:
   where truth lives, what requirement and scenario headings look like, and
   which command validates them.

4. **Detection precedence is hard, not advisory.** When `openspec/` exists in
   the target repository it is the specification home. The workflow may not
   create `requirements/`, `.kiro/specs/` or `spec/` beside it, and may not
   demote OpenSpec because a ticket, planner classification or compaction
   summary suggests another layout.

5. **A variant declares prerequisites it cannot install.** `spec/openspec`
   states the global package install, the Node.js floor, the `openspec init`
   step and the six generated capabilities, in the same way the `adr` profile
   already declares that it requires `docs/architecture/decisions/` in the
   consumer. A missing prerequisite is reported as a prerequisite gap; it is
   never silently downgraded to another layout.

6. **Absorption is a field, not a sentence.** `superseded_by` becomes
   mandatory for `class: state` with `status: superseded` or `deprecated`,
   not only for sealed events, and a new `DOC-G6` fails when two specification
   homes hold content at once. An agent will eat prose but must respect a
   field.

## Consequences

- A consumer selects its specification home once, the same way it selects a
  transport or a language, and can switch later with `select --reinstall`.
- The neutral spine stays in `core/`, so a consumer that selects no variant
  keeps the lifecycle and loses only the layout binding. Moving the whole
  workflow into the family would have repeated the ADR-0007 migration cliff,
  where an empty profile list silently drops the moved files.
- `truth-pipeline` and `sdd-workflow` stop competing: `truth-pipeline` keeps
  the migration and shadow-rollout protocol, `sdd-workflow` keeps the phase
  lifecycle, and neither declares a path layout of its own.
- Enforcing `superseded_by` on superseded state documents is a ratchet.
  Existing consumers with such documents will fail `DOC-G2` until they name
  what superseded them — deliberate, because today that claim is unverifiable.
- The harness gains a dependency it does not control. When a consumer selects
  `spec/openspec`, its validation gate is an external CLI whose version is not
  pinned by the receipt. The receipt covers the binding text, not the tool.

## Implementation status

Built in `v0.3.0-rc.1`: the `spec/` family with its three bindings, the neutral
spine in `core/skills/sdd-workflow`, the artifact-role aliasing that keeps the
existing authoring rules correct under any home, `DOC-G6`, and the `DOC-G2`
requirement that a superseded or deprecated state document declare
`superseded_by`.

Deliberately not done: the thirteen authoring rules still say `requirements.md`,
`design.md`, `tasks.md` and `research.md` in roughly forty places. Rewriting
that prose was rejected as a large, risky diff over well-tuned text. Instead
those four names are defined as **roles** that the binding resolves, so the
rules stay correct under every home without being touched. A reader who takes
them as file names in an OpenSpec repository is reading against the spine.
