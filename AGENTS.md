# Agent instructions

Read `docs/INDEX.md` before changing governance behavior. A rule, gate,
manifest schema, ownership boundary or release behavior change requires an ADR
and CHANGELOG entry in the same commit.

Keep `core/` project-neutral. Project names, absolute home paths, credentials,
component names and tracker endpoints are forbidden there. Profiles may name a
technology stack, never a consumer repository.

Run the stdlib unit suite, source verifier and manifest reproducibility check
before committing. Never call a release production-ready while
`docs/HARDENING.md` reports a gap.

