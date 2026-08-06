# Hardening status

Production certification: **NO-GO**

The repository is private and release archives are sha256-verifiable, but the
current GitHub account does not provide the required protected private
`main`/ruleset tier and release tags are not cryptographically signed. Tags
therefore use release-candidate versions only.

The hosted runner is allocated as of 2026-08-04 and the source workflow runs
green: unit suite, source verifier and manifest reproducibility. The earlier
billing/spending prerequisite is resolved, so local evidence is no longer the
only evidence available.

That closes runner allocation, not branch protection. The workflow has been
observed green on a feature branch; nothing yet *requires* it to pass before a
merge, so a red run cannot currently block one.

Promotion requires all of:

- protected `main` with required review and required CI;
- ~~an enabled hosted/self-hosted runner with a green source workflow~~ — met
  2026-08-04;
- CODEOWNERS enforcement for `core/rules/`, `core/gates/`, `harness.py` and
  release tooling;
- cryptographically signed, verified release tags — the verification mechanism
  now exists (ADR-0012) but no key is published, so releases are still unsigned;
- a clean external pilot loop for the exact candidate.

Absence of those controls is reported as a prerequisite gap, not waived by a
green unit test.
