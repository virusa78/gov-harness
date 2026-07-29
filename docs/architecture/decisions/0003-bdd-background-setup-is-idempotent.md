# ADR-0003: BDD Background setup is idempotent

## Status

Accepted — 2026-07-29

## Context

ADR-0002's pilot loop removed assertions and irreversible mutations from BDD
Background. The pilot's next review found that reversible but non-idempotent
setup can still make repeated or reordered scenarios observe different state.

## Decision

BDD Background may establish shared preconditions only through idempotent
setup. Repeating the Background or running scenarios in a different order
must not change the observed result.

## Consequences

Executable acceptance scenarios remain independently repeatable and parallel
runs do not inherit hidden sequence coupling. Test setup that cannot be made
idempotent belongs in an isolated per-scenario fixture with explicit teardown,
not in shared Background.

