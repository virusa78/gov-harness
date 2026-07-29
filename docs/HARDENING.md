# Hardening status

Production certification: **NO-GO**

The repository is private and release archives are sha256-verifiable, but the
current GitHub account does not provide the required protected private
`main`/ruleset tier and release tags are not cryptographically signed. Tags
therefore use release-candidate versions only.

Promotion requires all of:

- protected `main` with required review and required CI;
- CODEOWNERS enforcement for `core/rules/`, `core/gates/`, `harness.py` and
  release tooling;
- cryptographically signed, verified release tags;
- a clean external pilot loop for the exact candidate.

Absence of those controls is reported as a prerequisite gap, not waived by a
green unit test.

