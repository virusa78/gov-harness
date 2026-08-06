# ADR-0014: A completion claim is a record, and it goes stale

## Status

Accepted — 2026-08-06

## Context

Thirteen checks in this release fail closed, and every one of them checks the
same kind of thing: whether the repository's *state* is what it claims to be. A
rule cannot be edited unnoticed, a skill cannot be hand-copied, a document
cannot claim its content moved without naming where.

Nothing checks whether the *work* is done.

Thirteen authoring rules — EARS, gap analysis, design principles, tasks
generation, the review gates — are prose an agent may read and disregard, and
`sdd-workflow` states the failure mode in its own words: never infer
implementation from file presence, plausible syntax, an exit code alone, or an
agent's completion statement. That is an accurate description of the mistake
and a request not to make it. Requests are not gates, which is the whole
argument of `truth-pipeline` law 12.

The evidence from building this release is blunt. Nine mistakes were made
during it. The gates caught three — a decision missing from its index, a
manifest left stale after a source edit, bytecode scanned as source. The other
six were caught by executing something against reality: running a documented
command and finding it blocked, installing into a live project and watching a
schema bump silently disable profile exclusivity, comparing file modes against
the upstream they came from, building a dependency graph from actual files
instead of a README.

Documents did not prevent those. Execution against real state did.

## Decision

**A completion claim is a record produced by running something, and it expires
when the code changes.**

1. **Evidence is recorded by a runner, not written by hand.**
   `verify-evidence.py record --requirement ID -- <command>` executes the
   command and appends what happened: the command, its exit code, a digest of
   its output, the commit the tree was at, and when. A failing command produces
   a failing record, deliberately — the recorder reports, it never judges.

2. **Evidence is bound to a commit, so it goes stale.** A record made before
   the current commit is not evidence for the current code. This is the
   load-bearing rule and it is nearly free: no re-execution is needed to know
   that proof predates the thing it claims to prove. It refuses "I tested it
   earlier", "it worked before the refactor" and "I am confident it passes"
   without running anything.

3. **A phase is refused, not warned.** `verify` fails when any requirement in
   the specification home has no record, only stale records, or only failing
   ones. Evidence naming a requirement that no longer exists is also a finding:
   the journal and the specification are checked against each other in both
   directions.

4. **`--replay` converts a record back into an observation.** It re-runs each
   recorded command and compares the exit code. Without it a hand-written
   record passes the cheap check; with it, fabrication is caught. Both modes
   are offered because their costs differ by orders of magnitude and pretending
   otherwise would push consumers to disable the gate entirely.

5. **A corrupt journal fails the gate.** An unparseable line is not skipped.
   A journal that cannot be read in full cannot certify anything, which is the
   fail-closed reading `truth-pipeline` already applies to its own log.

6. **Requirement discovery belongs to the specification home.** The gate reads
   `spec_home` and a configured pattern, so it works under whichever binding
   ADR-0008 selected. No pattern configured means the gate skips and says so.

## Consequences

- "Done" stops being a sentence an agent can produce and becomes a file an
  operator can read. The question changes from *did it say it tested this* to
  *which command, what exit code, at which commit*.
- Every meaningful change now invalidates evidence, which is the intended cost.
  A refactor that touches nothing behavioural still expires every record, and
  re-running is the price of the guarantee. Consumers who find that too
  expensive will narrow `requirement_pattern` rather than lie, and that
  narrowing is visible in the policy.
- The cheap check is honestly weaker than the expensive one. A record whose
  exit code was typed rather than observed passes `verify` and fails
  `verify --replay`. This is stated rather than hidden: a green `verify` proves
  a record exists at this commit, not that the command was ever run.
- The gate proves a command succeeded. It does not prove the command was the
  right command, or that the requirement it names is the one it exercises.
  That is reviewer judgment, and no amount of journal makes it mechanical.
- Evidence is project truth: it lives in the consumer's repository, is never
  distributed, and the harness only ships the tool that writes and reads it.

## Implementation status

Built in `v0.8.0-rc.1`: `core/gates/verify_evidence.py` shipping as
`scripts/verify-evidence.py`, the `evidence_journal`, `requirements_source` and
`requirement_pattern` policy keys, and `tests/test_evidence.py` covering a
missing record, a real exit code captured, a failing record refused, freshness,
staleness after a commit, re-recording, fabrication caught by replay, a corrupt
journal, evidence for a deleted requirement, the unconfigured skip, and a
refusal to record outside a repository.

Not built: binding the gate to a phase automatically. Running it remains the
consumer's step in their own CI, because the harness does not own their
pipeline.
