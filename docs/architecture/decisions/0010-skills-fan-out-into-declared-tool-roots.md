# ADR-0010: Skills fan out into declared agent tool roots

## Status

Accepted — 2026-08-04

## Context

ADR-0007 built the fan-out mechanism — manifest `targets`, per-file `fanout`,
per-target parameter overlays — precisely so that one release could serve
several agent tools whose skill roots differ. It then declared no targets. Every
manifest from the first release to `v0.3.0-rc.1` carries `targets: []`, and
`.agents/skills` was the only skill destination.

The mechanism therefore existed and was unreachable. A user of a different
agent tool had no supported install path, and did the only thing the
documentation made possible: copied all eight skill directories into a global
`~/.codex/skills/`. That produces no `.harness.lock`, so no receipt, no drift
detection and no stray detection — the entire value of the harness. It also
breaks silently: a skill links its rules as
`../../../docs/governance/rules/<name>.md`, which resolves to the project root
from `<root>/<skill>/SKILL.md`, but from a home directory resolves to
`/home/<user>/docs/...`, where nothing exists. Every rule reference dangles and
nothing says so.

Both tools this repository is used with load skills from a project-local
directory as well as a personal one: Claude Code reads `.claude/skills/`,
Codex reads `.codex/skills/`. A project-scoped install is therefore possible
for both, and is the one that can carry a receipt.

## Decision

1. **Declare targets.** The manifest declares `agents` (`.agents/skills`),
   `claude` (`.claude/skills`) and `codex` (`.codex/skills`). Skill files are
   `fanout`, with destination `{{target_root}}/<path>`; one source installs
   into every selected root. `.agents/skills` is retained so existing
   consumers keep their layout.

2. **Every target root is also a managed root.** A hand-copied skill in any of
   them is reported as a stray by `check` and pruned by `init --reinstall`.
   The failure that started this now fails loudly.

3. **A target root is exactly two path segments.** A skill's rule links only
   land on the project root from `<root>/<skill>/SKILL.md` when the root has
   two segments; a three-segment root would point every rule link one level
   above the project with no error anywhere. `tests/test_targets.py` holds the
   invariant, and separately resolves every shipped relative link against
   every declared root.

4. **No `target_params`.** Nothing currently shipped differs per tool, and
   this repository's own design-synthesis rule forbids components that exist
   for hypothetical future requirements. The overlay stays available in the
   format for the release that first needs it.

5. **`SKILL-G` accepts several roots.** `skills_root` may be a string or a
   list. A listed root that does not exist is skipped, so selecting a subset
   of targets stays quiet; if no listed root exists at all, that is a finding.

## Consequences

- The default install now writes three skill trees. A consumer that wants one
  passes `--target <name>` to `init`; the selection is recorded in the lock and
  honoured by later syncs.
- A consumer of `v0.3.x` gains `.claude/skills/` and `.codex/skills/` on a plain
  `sync`, because an old lock records no targets and the installer then selects
  all declared ones. To narrow the selection, reinstall with `--target`; `sync`
  has no target flag by design, since changing what is installed is a selection
  change rather than an update.
- The same bytes now exist in up to three places in a working tree. That is
  duplication on disk, accepted because each tool only reads its own root and
  the receipt covers every copy.
- Adding a fourth tool is a manifest edit plus an ADR-worthy check that its
  root is two segments deep. A tool that insists on a deeper root cannot be
  served without changing the link convention inside every skill.
- Personal, machine-level installs (`~/.codex/skills`, `~/.claude/skills`)
  remain out of scope and unsupported. They cannot carry a project receipt and
  cannot see project-local rules, so the harness has nothing to guarantee
  there.
