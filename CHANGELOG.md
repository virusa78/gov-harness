# Changelog

## Unreleased

- Decide that the specification home is an exclusive profile axis, that
  OpenSpec takes precedence where it exists, and that absorption into it is a
  frontmatter field rather than prose (ADR-0008). No release behavior changes
  yet; the ADR records its own implementation gap.
- Repair the source workflow: it pinned `v0.1.0-rc.5` against a `v0.2.0-rc.1`
  manifest, so the reproducibility check failed, and it ran only
  `tests/test_harness.py`. CI and the README now discover every test module,
  and `tests/test_release_pins.py` fails offline when a documented pin drifts
  from the manifest version.
- Correct README drift from `v0.2.0-rc.1`: the `select` command and the
  profile families were missing.

## v0.2.0-rc.1 — 2026-08-03

- Manifest schema 2: profile families (`family/variant`), mutually exclusive
  selection, shared destinations between variants of one family, targets with
  per-target parameter overlays, per-file fan-out, managed roots with
  transactional stray pruning, and `profile_info` menu metadata (ADR-0007).
- `harness.py select`: interactive stack menu rendered entirely from manifest
  data; `--choose family=variant` non-interactive form; `--print-only`;
  `init --reinstall` converges an installed project.
- Move stack content out of core: `io-resilience` ships as
  `transport/nats` / `transport/kafka` variants of one canonical rule path;
  `python-testing-gate` becomes `testing/python-tools` with its foreign
  repository claims neutralized; `adr` becomes the standalone `adr` profile;
  `csharp-fintech` becomes `lang/csharp-fintech`.
- Fix the dangling source pointer in the `karpathy` skill and genericize the
  broker example in `bdd-format`.
- Schema 1 releases install exactly as before; their locks stay byte-identical.

## v0.1.0-rc.8 — 2026-07-29

- Adopt the consumer-born generated-document lifecycle.
- Require generator identity and source digest for every GENERATED document.

## v0.1.0-rc.7 — 2026-07-29

- Record executable mode in release entries and project receipts.
- Apply executable mode transactionally and detect mode-only drift offline.
- Refuse `init --adopt-existing` when content matches but executable mode does
  not.

## v0.1.0-rc.6 — 2026-07-29

- Add lifecycle frontmatter to all fourteen canonical rules so consumer
  metadata ratchets do not increase.
- Distribute generic DOC-G3 stub and SKILL-G boundary verifiers.
- Refuse a new release destination that collides with differing unmanaged
  project content; accept byte-identical target convergence.

## v0.1.0-rc.5 — 2026-07-29

- Accept the second pilot-born BDD clarification: shared Background setup must
  be idempotent.
- Use this release to prove RC4 target-convergence through ordinary `sync`
  without `--force-theirs`.

## v0.1.0-rc.4 — 2026-07-29

- Adopt the pilot-born BDD clarification: Background may contain neither
  assertions nor irreversible mutations, so scenario order cannot affect
  results.
- Let `sync` accept old-lock drift when local bytes already equal the reviewed
  target release, completing the drift → adopt → release → sync loop without
  `--force-theirs`.

## v0.1.0-rc.3 — 2026-07-29

- Make `adopt` patch upstream `origin` paths from the lock instead of consumer
  destinations.
- Record destination-to-origin mappings in adopt metadata.
- Refuse automatic reverse-adoption of rendered templates because the
  project-specific value cannot be generalized safely.

## v0.1.0-rc.2 — 2026-07-29

- Resolve private release assets through the GitHub release API instead of the
  browser download URL, which returns 404 for private assets even with Bearer
  authentication.
- Drop authorization when a signed asset redirect crosses to a storage host.
- Preserve RC status and all RC1 hardening gaps.

## v0.1.0-rc.1 — 2026-07-29

- Establish the core/profile/local ownership boundary.
- Add the stdlib `init`, `sync`, `check`, `diff` and `adopt` CLI.
- Package fourteen canonical rules, six generic skills and the
  `csharp-fintech` two-skill profile.
- Add deterministic manifest/archive generation and reusable receipt CI.
- Mark the release pre-production while private branch protection and tag
  signing remain unavailable.
- Record the hosted-runner billing/spending prerequisite after GitHub refused
  to allocate the initial CI job.
