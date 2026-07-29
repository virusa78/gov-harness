# Changelog

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
