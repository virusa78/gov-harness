# ADR-0005: Receipts cover executable mode

## Status

Accepted — 2026-07-29

## Context

The first consumer checkpoint proved content hashes but showed that staged
installation normalized every managed file to mode `0644`. Shell and Python
entrypoints therefore lost their executable bit while `check` still reported
clean.

## Decision

Every release entry and lock receipt records an `executable` boolean.
Installation applies mode `0755` or `0644` accordingly, and offline `check`
treats a mode mismatch as drift.

## Consequences

The receipt now proves both content and the only portable mode distinction the
harness needs. Same-version sync can repair explicit mode drift through the
existing drift policy, and `init --adopt-existing` refuses a mode mismatch.
