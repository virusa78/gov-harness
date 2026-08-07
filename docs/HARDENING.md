# Hardening status

Production certification: **NO-GO**

The repository is private and release archives are sha256-verifiable, but the
current GitHub account does not provide the required protected private
`main`/ruleset tier and release tags are not cryptographically signed. Tags
therefore use release-candidate versions only.

The source workflow runs green when it runs at all: unit suite, source verifier
and manifest reproducibility. The earlier billing/spending prerequisite is
resolved, so local evidence is no longer the only evidence available.

Runner allocation is availability, not an achievement, and it has already been
observed to come and go:

| when (UTC) | state | evidence |
| --- | --- | --- |
| 2026-08-04 | allocated | first green source workflow |
| 2026-08-06 17:49 → 20:29 | starved | every run executed zero steps and was cancelled after exactly 15 minutes; last run to reach a runner was `4f0c380` at 16:48 |
| 2026-08-06 20:31 → 2026-08-07 05:47 | no runs created at all | pushes and pull requests produced no workflow run to inspect |
| 2026-08-07 05:47 | allocated | `aba98df` on `main`, run [31151770889](https://github.com/virusa78/gov-harness/actions/runs/31151770889), all six steps green in 17s |

Two outage shapes matter here because they read identically to a reader who
only looks at a badge:

- a **queued-then-cancelled** run looks like a red check and is not one — it is
  an absence of evidence with no steps behind it;
- **no run at all** looks like a clean history and is the same absence, minus
  the trace.

Manual dispatch (`workflow_dispatch`) is the remedy for the second shape: it is
how you ask for a run on a commit GitHub never built. It queues the run; it
cannot conjure a runner, so it does nothing for the first shape.

`main` is currently verified: `aba98df` passed unit suite, source verifier and
manifest reproducibility on a hosted runner.

Runner allocation aside, nothing yet *requires* the workflow to pass before a
merge, so a red run cannot currently block one.

Promotion requires all of:

- protected `main` with required review and required CI;
- an enabled hosted/self-hosted runner with a green source workflow — held
  2026-08-07, but it lapsed once already and nothing here guarantees it holds
  tomorrow, so it stays on this list until CI is *required* and an unavailable
  runner therefore blocks a merge instead of passing unnoticed;
- CODEOWNERS enforcement for `core/rules/`, `core/gates/`, `harness.py` and
  release tooling;
- cryptographically signed, verified release tags — verification exists
  (ADR-0012) and the custody procedure is written down (`docs/SIGNING.md`), but
  no key has been generated, so releases are still unsigned. The key must be
  created on the release machine and never transmitted;
- a clean external pilot loop for the exact candidate.

Absence of those controls is reported as a prerequisite gap, not waived by a
green unit test.
