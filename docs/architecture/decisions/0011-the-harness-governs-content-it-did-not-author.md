# ADR-0011: The harness governs content it did not author, by static composition

## Status

Accepted — 2026-08-06. This ADR records the decision; nothing described here is
built yet (see Implementation status).

## Context

The release can only distribute files from its own source tree. Every rule,
skill and gate in `core/` and `profiles/` is authored here. Useful doctrine
that exists elsewhere — a debugging discipline, a worktree workflow, a
third-party skill catalogue — has no way in, so a consumer who wants both
installs the harness *and* a plugin manager, and gets two distributors writing
into the same directories with different guarantees.

That is not a hypothetical. ADR-0010 made every agent tool skill root a managed
root, so a project-scoped plugin installed into `.claude/skills/<plugin>/` is
now reported as a stray and pruned on the next `sync` unless the consumer knows
to claim the path with an `--override`.

Meanwhile the wider ecosystem has demonstrated what happens without the
guarantees this harness already provides. Through 2026 the agent-skill
marketplaces absorbed large-scale supply chain attacks — malicious skills
published at scale, credential harvesters, instructions that survived skill
removal — and are now retrofitting exactly the controls the receipt has carried
since `v0.1.0`: published checksums, publisher pinning, per-skill version
pinning, frozen installs verified by content hash. The named failure modes were
*silent override* and *blind bulk update*: content changing underneath an
operator who never asked for a change.

The harness has the receipt and cannot reach foreign content. The marketplaces
have the content and are still building the receipt. The gap worth closing is
the first one, and only in the direction that does not import the second one's
failure modes.

## Decision

**Foreign content is composed statically, never fetched live.** Bytes from
another repository are vendored into this source tree at a pinned commit, where
they become ordinary release sources indistinguishable at install time from
content authored here. There is no resolution step, no dependency graph, and no
moment at which a consumer's machine contacts a foreign host.

1. **Vendored, in-tree, pinned.** Foreign files live under
   `vendor/<upstream>/` and are committed. The manifest declares the upstream
   once:

   ```json
   "upstreams": [
     {
       "name": "superpowers",
       "repo": "https://github.com/obra/superpowers",
       "commit": "<40-hex>",
       "license": "MIT",
       "license_path": "vendor/superpowers/LICENSE"
     }
   ]
   ```

   A commit, never a branch or a tag: a tag can move, a branch always does.

2. **Two digests per vendored file.** `sha256` is the bytes as shipped;
   `upstream_sha256` is the bytes as fetched at `commit`. Equal digests mean an
   unmodified copy. Different digests mean this release carries a local patch,
   which is then a visible, reviewable fact rather than a silent divergence —
   the `adopt` semantics of ADR-0002 generalised from consumer drift to
   upstream drift.

   ```json
   {
     "source": "vendor/superpowers/skills/systematic-debugging/SKILL.md",
     "destination": "{{target_root}}/systematic-debugging/SKILL.md",
     "upstream": "superpowers",
     "upstream_path": "skills/systematic-debugging/SKILL.md",
     "upstream_sha256": "sha256:...",
     "sha256": "sha256:...",
     "fanout": true,
     "layer": "profile",
     "profile": "workflow/superpowers"
   }
   ```

3. **The installer never fetches from an upstream.** `harness.py` gains no
   network behaviour whatsoever. It continues to acquire exactly one archive
   from its own release and verify it against the receipt. Vendored content
   arrives inside that archive like everything else.

4. **Refreshing an upstream is a maintainer operation, offline and reviewed.**
   A separate tool re-fetches at a new commit, recomputes both digests, and
   reports which vendored files changed and which local patches no longer
   apply. It runs in this repository, produces an ordinary commit with an
   ordinary diff, and lands through ordinary review. It is never automatic,
   never scheduled, and never reachable from a consumer. A refresh that cannot
   be read as a diff is a blind bulk update wearing a different hat.

5. **Foreign content is always `profile`, never `core`.** `core/` is what this
   repository authors and vouches for as invariant. Vouching for bytes written
   elsewhere is a claim it cannot support, so vendored content is opt-in by
   profile selection like any other stack choice.

6. **Overlap is declared, not discovered.** ADR-0008 established that two
   artifacts may not both own one lifecycle. A profile that vendors foreign
   skills must state, for each skill that overlaps an existing capability,
   which one is authoritative; the loser carries `superseded_by` naming the
   winner. A vendored skill that silently competes with `sdd-workflow` for the
   planning lifecycle is the second head of truth this project spent ADR-0008
   removing.

7. **Provenance is mandatory.** An upstream without a license, or a vendored
   tree whose license file is not vendored alongside it, fails the source
   verifier. The consumer receives the license with the bytes.

## Consequences

- A consumer gets foreign doctrine under the same receipt as everything else:
  pinned version, per-file digest, drift detection, stray pruning, and the
  refusal to overwrite unmanaged content. The distinction between "our rule"
  and "their skill" disappears at install time and survives only as metadata.
- The `.claude/skills` collision stops being a dilemma. Content the harness
  vendors is receipt-owned rather than a stray, so it is no longer a choice
  between pruning a plugin and carving an override out of a managed root.
- This repository takes on a maintenance burden it did not have: a vendored
  upstream that moves is work, and a vendored upstream that dies is a fork.
  That cost is the price of the guarantee and must not be hidden — an upstream
  nobody is willing to refresh should not be vendored in the first place.
- Release archives grow by the size of everything vendored. Acceptable; the
  archive is already the unit of trust.
- Consumers cannot pull a newer upstream faster than this repository ships one.
  That is the intended trade: no live updates means no surprise updates, and
  the lag is visible as a version number rather than invisible as drift.
- Manifest schema moves to 3. Schema 1 and 2 manifests keep their exact prior
  behaviour, as they did across ADR-0007.

## Implementation status

Built in `v0.5.0-rc.1`: manifest schema 3 with `upstreams` and the
`upstream`/`upstream_path`/`upstream_sha256` file fields, `scripts/vendor_upstream.py`
for fetch and offline check, vendored-tree verification in
`scripts/verify_source.py`, and the first vendored profile,
`workflow/superpowers`, at commit `44c9b2d6` under MIT.

Two things the first vendoring taught, recorded because the next one will hit
them too:

- **Upstream cross-references are a closure problem.** These skills address
  each other through the publisher's plugin namespace. Vendoring a subset
  chosen by usefulness would ship files pointing at capabilities the consumer
  never receives — a dangling reference of exactly the kind this project keeps
  finding. The vendored set must be closed under those references, and the
  namespace prefix is rewritten to the bare skill name because the plugin
  namespace does not exist in a plain install. That rewrite is the first real
  use of the second digest.
- **Executable mode does not survive a naive copy.** Upstream ships helper
  scripts with no file extension, so the suffix heuristic that serves authored
  content infers the wrong mode. The vendor record carries the mode explicitly,
  which ADR-0005 already required of every receipt.

Not built: signature verification of the release itself, which is a separate
and now more urgent gap (`docs/HARDENING.md`).
