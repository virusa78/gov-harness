# ADR-0002: A reviewed target release explains matching local drift

## Status

Accepted — 2026-07-29

## Context

The persistent pilot changed a managed BDD rule and produced an adopt patch.
After upstream accepts that exact change and publishes a release, the
consumer's file differs from its old lock but already equals the new target.
Refusing the sync at that point would require `--force-theirs` even though
there is no unexplained difference.

## Decision

`sync` validates the target release before deciding whether old-lock drift is
unexplained. A drifted destination whose current bytes exactly equal the
target payload is converged and may proceed. Missing files, removed target
files, or bytes that differ from both old and target remain unexplained and
are refused unless the caller explicitly uses `--force-theirs`.

The comparison is exact bytes after parameter rendering. It does not infer
semantic equivalence.

## Consequences

The full adopt loop completes without a destructive-looking override:
drift → patch → upstream review → release → ordinary sync. Sync still fails
closed for every change the reviewed target does not explain. The target must
be acquired and integrity-validated before refusal classification, so sync may
perform network I/O before reporting unexplained local drift; no project bytes
are changed during that validation.

