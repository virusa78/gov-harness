# ADR-0016: An unconfigured gate skips and says so

## Status

Accepted — 2026-08-07

## Context

Installing the `adr` profile on the pilot produced this, on day one, before the
project had done anything:

```
$ python3 scripts/verify-adr.py --root .
ADR-G CONFIG: decisions directory does not exist: docs/architecture/decisions   (exit 2)
```

The profile ships a skill and a gate and no scaffolding. There is nothing for
the project to have done wrong yet — it has written no decisions — and the gate
is red.

The same release is not consistent about this. `EVID-G` prints
`SKIP EVID-G: requirements_source ... are not configured` and exits 0.
`DOC-G4` prints `SKIP DOC-G4: explicit --base was not supplied` and is skipped.
The ADR *skill* even anticipates the directory being absent and tells the agent
what to do about it. Only the ADR gate treated "not yet in use" as a failure.

A gate that is red from the first minute is worse than a missing gate. It
trains the reader that red is the normal colour, and the next red — a real one
— reads the same. That is the mechanism by which a check stops being a check
while still running on every commit.

## Decision

**Absence of the thing a gate governs is a skip, not a failure — but only at
the default location.**

`ADR-G` now returns 0 with `SKIP ADR-G: <dir> does not exist, so no decisions
are recorded yet. Create the directory to activate this gate.`

Three boundaries make the skip safe:

- **Only for the default path.** An explicit `--decisions docs/adr` is an
  assertion by the caller that decisions live there. A path the caller named
  and that is not present is a configuration error and still exits 2.
- **Only for absence.** An empty directory activates the gate. Creating the
  directory is the deliberate act that switches enforcement on, which gives the
  project a single, visible moment where it opts in.
- **The skip is announced on stderr.** A silent skip and a pass are
  indistinguishable in a log, and the whole reason this file exists is that
  those two must never look alike.

## Consequences

A project can install the `adr` profile, read the skill, and adopt ADRs later,
without a red gate in between.

A project that deletes `docs/architecture/decisions` — losing every decision it
ever recorded — gets a skip rather than an alarm. That is the real cost, and it
is accepted because the receipt already covers it: the directory is not
harness-managed, so its contents were never something `check` claimed to
protect, and a project that deletes its own decisions is not being deceived
about anything.

The rule generalises: every gate in this release now treats "not configured"
and "configured and violated" as different answers, and prints which one it
gave.
