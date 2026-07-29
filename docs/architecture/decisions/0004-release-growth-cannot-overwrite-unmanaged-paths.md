# ADR-0004: Release growth cannot silently overwrite unmanaged paths

## Status

Accepted — 2026-07-29

## Context

The first superfront2back installation exposed two release-growth cases. New
canonical rules participate in the consumer's lifecycle gate, so they require
metadata at their source. New generic gates can also land at destinations that
already contain a project-born implementation not present in the old receipt.

Treating either case as an ordinary overwrite would create an unexplained fork
or silently destroy local work.

## Decision

Every distributed Markdown rule carries lifecycle frontmatter before release.
During sync, a destination absent from the old receipt may be adopted by the
new receipt only when it is absent, already byte-identical to the reviewed
target, or the operator explicitly selects `--force-theirs`.

## Consequences

Consumer metadata ratchets do not increase when a rule pack is installed.
Project-born generic gates can converge into a later release without a forced
overwrite when the bytes are identical. A differing unmanaged destination
fails closed and names the collision.
