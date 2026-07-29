# Changelog

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
