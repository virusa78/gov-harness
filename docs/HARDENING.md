# Hardening status

Production certification: **NO-GO**

The repository is private and release archives are sha256-verifiable, but the
current GitHub account does not provide the required protected private
`main`/ruleset tier and release tags are not cryptographically signed. Tags
therefore use release-candidate versions only.

The source workflow runs green when it runs at all: unit suite, source verifier
and manifest reproducibility. The earlier billing/spending prerequisite is
resolved, so local evidence is no longer the only evidence available.

**Runner allocation regressed on 2026-08-06 and is not currently met.** Every
run queued after 17:49 UTC that day — pushes, pull requests and the manual
dispatch on `main` — executed zero steps and was cancelled by GitHub after
exactly 15 minutes of waiting for a runner. The last run that reached a runner
was `4f0c380` at 16:48 UTC (9 steps, green). Nothing about the workflow file or
the commits under test changed between them, so this is capacity, not content.
It is recorded here rather than waived because a queued-then-cancelled run
looks like a red check and is not one: it is an absence of evidence.

Manual dispatch (`workflow_dispatch`) works and is the way to ask for a run on
a commit GitHub never built. It queues the run; it cannot conjure a runner.

Runner allocation aside, nothing yet *requires* the workflow to pass before a
merge, so a red run cannot currently block one.

Promotion requires all of:

- protected `main` with required review and required CI;
- an enabled hosted/self-hosted runner with a green source workflow — met
  2026-08-04, regressed 2026-08-06 (see above), open again;
- CODEOWNERS enforcement for `core/rules/`, `core/gates/`, `harness.py` and
  release tooling;
- cryptographically signed, verified release tags — verification exists
  (ADR-0012) and the custody procedure is written down (`docs/SIGNING.md`), but
  no key has been generated, so releases are still unsigned. The key must be
  created on the release machine and never transmitted;
- a clean external pilot loop for the exact candidate.

Absence of those controls is reported as a prerequisite gap, not waived by a
green unit test.
