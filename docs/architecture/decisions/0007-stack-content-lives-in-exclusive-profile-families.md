# ADR-0007: Stack content lives in mutually exclusive profile families

## Status

Accepted — 2026-08-03

## Context

Core shipped stack-specific content to every consumer. The Kafka/Redpanda
variant of `io-resilience` and the Kafka-flavoured `python-testing-gate`
landed unmodified in a NATS/C++ repository, where their factual claims were
false and their guidance misleading. The AGENTS.md rule "keep core
project-neutral" had no structural enforcement: neutrality was a review
convention, not a property of the release format.

Separately, one release had to serve several agent tools (Claude, Codex,
Cursor, Antigravity) whose skill roots and invocation dialects differ, and
repeated installs had no way to converge: files from earlier layouts or
hand-copied skill trees stayed behind and drifted silently.

## Decision

Manifest schema 2, implemented in `harness.py` and produced by
`scripts/build_manifest.py`:

1. **Profile families.** A profile name may be `family/variant`
   (`transport/nats`). Selection accepts at most one variant per family;
   violations are refused. Profiles without a family stay standalone
   multi-select toggles. Two variants of one family may declare the same
   destination — the canonical rule path is stable while the selected profile
   supplies its content. Cross-family destination sharing remains refused.
2. **Stack content leaves core.** `core/` holds only stack-neutral rules and
   skills. Stack-specific content lives under `profiles/<family>/<variant>/`
   or `profiles/<standalone>/` with `skills/` and `rules/` subtrees.
   `scripts/verify_source.py` enforces the inventory fail-closed.
3. **Targets and fan-out.** The manifest may declare targets (tool roots with
   per-target parameter overlays) and per-file `fanout` so one source installs
   into every selected tool root with the tool's own invocation dialect.
4. **Managed roots.** Subtrees listed in `managed_roots` are owned by the
   harness: receipt-unowned, override-unprotected files inside them are
   reported by `check` as strays and pruned by `init --reinstall`/`sync`
   transactionally.
5. **The menu is data.** `harness.py select` renders the stack menu purely
   from the manifest (`profile_info` plus declared profiles). The harness
   binary carries no stack knowledge; every project runs the identical
   harness and differs only in its recorded selection.

Schema 1 manifests keep their exact prior behavior, and locks produced from
them stay byte-identical.

## Consequences

- A consumer selects its stack once (`--profile` flags or the menu) and can
  switch later with `select --reinstall`; the shared-destination rule swaps
  content in place.
- Consumers of v0.1.x receive moved content only after reinstalling with the
  matching profiles; a plain sync with an empty profile list would drop the
  moved files. The migration is deliberate, not silent.
- `PROFILE_INFO` in `build_manifest.py` is the single description source for
  the menu; an undescribed or phantom profile fails the manifest build.
