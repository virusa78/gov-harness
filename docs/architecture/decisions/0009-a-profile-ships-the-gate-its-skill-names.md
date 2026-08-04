# ADR-0009: A profile ships the gate its skill names

## Status

Accepted — 2026-08-04

## Context

The `adr` profile skill told the agent that a static gate named `ADR-G` lives
in `scripts/verify-requirements.sh`, and instructed it to run that script after
authoring a record. The script exists in neither the source repository nor any
release manifest. Nothing detected this: the release format had no place for a
profile to carry an executable, so a profile could only *describe* enforcement,
and the description drifted into a claim about a file that was never shipped.

The same shape appeared elsewhere. Three shipped gates default to
`docs/governance/docs-policy.json`, `skill-policy.json` and `stub-policy.json`
— project-owned configuration the release never provided and never documented,
so a fresh consumer received three executables that each failed with a
configuration error and no way to learn the schema.

Both are the failure `truth-pipeline` law 12 names: *gate, not discipline*. A
release that ships thirteen rules of requirement discipline and zero enforcement
of them is selling a doorbell as a forensic examiner.

## Decision

1. **A profile may carry a `gates/` subtree.** `profiles/<name>/gates/*.py`
   installs to `scripts/<dashed-name>.py` alongside the core gates, with the
   same receipt ownership and executable-mode integrity as any other release
   file. `scripts/build_manifest.py` discovers it and
   `scripts/verify_source.py` holds its inventory fail-closed.

2. **A skill may not name a gate the release does not ship.** If a profile
   claims enforcement, the executable travels with it. Where enforcement is
   genuinely the consumer's, the skill says so and names no path.

3. **A gate imposes no natural language.** Section headings and field names
   that a repository writes in its own language are arguments with documented
   defaults, never hardcoded assumptions. `ADR-G` therefore takes `--section`
   and `--lesson-field`.

4. **Consumer-owned configuration ships as an example, never as a managed
   file.** The release provides `docs/governance/*-policy.example.json` with the
   schema documented inside it; the consumer copies one to the real path and
   edits it. The copy is unmanaged, so consumer edits are configuration rather
   than drift, and a gate that cannot load its config points at the example.

## Consequences

- The `adr` profile now ships `scripts/verify-adr.py`, which checks unique
  decision numbers, required and non-empty sections, an index consistent in
  both directions, and a non-empty rule line per lesson. It is a form checker:
  it proves shape, never that a decision is right.
- Profile directories gained a third content kind. A directory under
  `profiles/` holding none of `skills/`, `rules/` or `gates/` is a family, and
  its children are its variants; that rule is unchanged apart from the new kind.
- Shipping configuration as an example rather than a managed file means the
  release cannot ratchet a consumer's policy forward. A tightened default
  reaches an existing consumer only when they re-copy the example, and the
  release notes have to say so.
- A gate whose defaults are English will report findings against a repository
  whose canon is not, until the consumer passes the flags. That is a visible
  argument in CI rather than a silent mismatch, which is the intended trade.
