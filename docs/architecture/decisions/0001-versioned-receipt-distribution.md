# ADR-0001: Distribute governance through a versioned receipt

## Status

Accepted — 2026-07-29

## Context

Manual copies of agent rules and skills lose provenance and fork silently.
Project ADRs, lessons, requirements and registries are local truth and cannot
be centralized without erasing ownership.

## Decision

Governance working doctrine is released from this repository as `core` plus
opt-in profiles. A stdlib CLI installs only manifest-declared destinations and
writes `.harness.lock` with per-file sha256 receipts, parameters and overrides.
Updates use an explicit tag. Local improvements return as an `adopt` patch for
upstream review; they never move sideways into another project.

Project truth and `local` policy are excluded from every release manifest.
Release tags remain candidates until protected private `main` and signed tags
are available.

## Consequences

Consumers receive deterministic provenance, mechanical drift detection and a
reviewable upgrade diff. The cost is an explicit release and sync step for
every shared change. Overrides become visible debt. The upstream must
dogfood ADR, changelog, ownership and release-integrity discipline.

