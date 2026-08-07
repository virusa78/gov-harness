# Hardening status

Production certification: **NO-GO**

Release archives are sha256-verifiable, but `main` is not protected and release
tags are not cryptographically signed. Tags therefore use release-candidate
versions only.

The tier objection recorded here earlier no longer applies: it assumed a
private repository, and rulesets on a private repository need a paid plan. This
repository is public, where rulesets are free. What blocks protection now is
access, not tier — see below.

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

`main` is currently verified: `235d7cf` passed unit suite, source verifier and
manifest reproducibility on a hosted runner, 9/9 steps.

## Branch protection

Runner allocation aside, nothing yet *requires* the workflow to pass before a
merge, so a red run cannot currently block one.

The configuration that fixes it is committed at `.github/rulesets/main.json`:
active enforcement on the default branch, no bypass actors, deletion and
force-push blocked, changes through pull requests, and the `verify` check
required in strict mode and pinned to the GitHub Actions app.

It is **not applied**. Applying it needs `administration: write`, which this
repository's automation deliberately does not hold, so it is a manual step by
the owner:

```bash
gh api --method POST repos/virusa78/gov-harness/rulesets \
  --input .github/rulesets/main.json
```

A committed JSON file describing protection proves nothing — that is the same
error as a status line standing in for a run nobody produced. So the claim is
checkable against the server:

```bash
GITHUB_TOKEN=<token with administration:read> \
  python scripts/check_branch_protection.py --repo virusa78/gov-harness
```

Exit 1 is drift, exit 0 is the live ruleset satisfying every claim in the file,
and **exit 2 is "could not tell" — not a pass**. Being unable to read the
configuration is indistinguishable from the configuration being absent. As of
2026-08-07 the checker reports drift: no such ruleset exists.

Two deliberate choices in that file:

- **`required_approving_review_count: 0`.** Requiring an approval on a
  single-maintainer repository blocks every merge, because GitHub does not let
  an author approve their own pull request. Required review stays an open
  prerequisite below rather than being faked with a number that cannot be met.
- **No bypass actors.** With none, an unavailable runner blocks merges to
  `main` outright. That is the intended behaviour, and the escape hatch is
  editing the ruleset — a deliberate, visible act, not a standing exemption
  that quietly applies every day.

Promotion requires all of:

- protected `main` with required CI — configuration written and checkable
  (`.github/rulesets/main.json`), not yet applied;
- required review on `main` — blocked on there being a second human, not on
  configuration;
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
