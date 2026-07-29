# ADR-0006: Generated documents have a distinct lifecycle

## Status

Accepted — 2026-07-29

## Context

The superfront2back W2 generator introduced deterministic manifests and
registries. Classifying them as mutable STATE would hide their generated
purity contract, while classifying them as sealed EVENT would prohibit normal
regeneration.

## Decision

The documentation lifecycle accepts `class: generated` only with
`status: current`. Generated documents must declare both `generator` and
`source_digest` in addition to the common metadata.

## Consequences

DOC-G2 distinguishes generated views from authored truth. DOC-G6 can reproduce
and compare those views, while a missing provenance or generator is a
mechanical failure rather than an editorial convention.
