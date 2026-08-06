# Changelog

## v0.6.0-rc.1 — 2026-08-06

Three defects found by installing over a live `v0.1.0-rc.8` pilot. None was
visible to the unit suite or the source verifier: each needed a real project
with a real prior install, which is lesson L4 applied rather than restated.

- `SKILL-G` reads receipt-owned skills from `.harness.lock` instead of making
  the policy restate them. An unedited example over a real install produced
  thirty findings, because the example listed four core skills and the project
  had fourteen. The lock already records the layer of each, so restating it was
  a second copy of the same fact and the first thing to rot when a profile
  selection changed. `skills` in the policy is now for local skills only; a
  receipt-owned skill may still be named there but must agree with the lock.
  Hand-copied skills are still caught.
- A profile may declare paths the consumer must already have, via `requires` in
  `profile_info`, and `init` refuses when they are absent. `adr` declared its
  need for `docs/architecture/decisions/` in prose only, so installing it into a
  project without one succeeded and failed later at the gate. Tool
  prerequisites the harness cannot see stay the binding's job to report.
- Refusing an unknown profile now names its replacement when one exists. A lock
  from `v0.1.x` says `csharp-fintech`, which ADR-0007 renamed to
  `lang/csharp-fintech`, and the old message left a migrating operator to find
  that in the changelog.

## v0.5.0-rc.1 — 2026-08-06

- Manifest schema 3: the release may carry content it did not author, vendored
  in-tree and pinned to a commit (ADR-0011). Files declare `upstream`,
  `upstream_path` and `upstream_sha256`; a shipped digest differing from the
  upstream digest is a recorded local patch rather than silent divergence.
  Schema 1 and 2 manifests keep their exact prior behaviour.
- The installer gains no network behaviour. `harness.py` never contacts an
  upstream; vendored bytes travel inside the same archive, under the same
  receipt, as everything else. A test asserts no upstream host appears in the
  installer at all.
- New profile `workflow/superpowers`: git worktree, subagent and code-review
  workflow vendored from obra/superpowers at `44c9b2d6` under MIT. The vendored
  set is closed under the upstream's cross-skill references, so no shipped file
  points at a capability the consumer does not receive, and the plugin
  namespace prefix is rewritten to bare skill names because that namespace does
  not exist in a plain install.
- `scripts/vendor_upstream.py`: `fetch` re-vendors at a commit and records both
  digests plus executable mode; `check` re-derives everything offline. Adding
  an upstream is an edit to the tool's declared set, so the list of foreign
  sources is visible in a diff. There is no automatic refresh.
- The vendor record carries executable mode explicitly. Upstream ships helper
  scripts with no extension, and the suffix heuristic used for authored content
  infers the wrong mode for them (ADR-0005).
- `verify_source.py` fails closed on a vendored tree: pinned 40-hex commit,
  declared and shipped license, and a record that matches the tree exactly.
  Every upstream license installs to `docs/governance/licenses/`.
- Fix three schema-2 hardcodes in `harness.py` that gated capabilities on
  `schema == 2` instead of a floor. Bumping to schema 3 silently disabled
  mutually exclusive profile families, which the first schema-3 install caught.
- Sign the release and verify it on install (ADR-0012). `package_release.py
  --sign-key` produces a detached Ed25519 signature over `SHA256SUMS`, and
  `harness.py --public-key` refuses an install whose signature is missing,
  invalid, or unverifiable. Until now the digest and the bytes it authenticated
  came from the same host, which proved transport integrity and not
  authenticity; the receipt closed that only from the second install onward.
  The verifying key is supplied by the consumer and never travels with the
  release, and the requirement is recorded in the lock so later syncs keep
  demanding it. Signing stays opt-in, so a project that passes no key behaves
  exactly as before.
- Record lesson L4: a mechanism nobody exercises is not a feature. Eight
  defects found in one audit shared a single cause — verification compared
  inventories instead of running a consumer's loop.

## v0.4.0-rc.1 — 2026-08-04

- Declare the fan-out targets ADR-0007 built the mechanism for and never used:
  `agents` (`.agents/skills`), `claude` (`.claude/skills`) and `codex`
  (`.codex/skills`). Skill files install into every selected root; `--target`
  narrows the selection and the lock records it (ADR-0010).
- Every target root is a managed root, so a hand-copied skill in any of them is
  reported as a stray instead of drifting invisibly. That was the failure this
  change exists for: with no supported install path, a skill tree had been
  copied into a global `~/.codex/skills/`, where it carried no receipt and
  every rule link inside it dangled.
- `SKILL-G` accepts a list of `skills_root` values. A listed root that is not
  installed is skipped so a target subset stays quiet; no installed root at all
  is a finding. A single string still works.
- No `target_params`: nothing shipped differs per tool yet, and the overlay
  stays available for the release that first needs it.

Consumers of `v0.3.x` gain `.claude/skills/` and `.codex/skills/` on a plain
`sync`, because an old lock records no targets and the installer then selects
every declared one. Reinstall with `--target` to narrow it; `sync` has no
target flag, since changing what is installed is a selection change rather than
an update.

## v0.3.0-rc.1 — 2026-08-04

- New `spec/` profile family: `spec/openspec`, `spec/kiro` and `spec/plain` are
  mutually exclusive bindings sharing the canonical rule path
  `docs/governance/rules/spec-home.md`, so a consumer switches its
  specification home with `select --reinstall` (ADR-0008).
- `core/skills/sdd-workflow` becomes the neutral spine: it names no
  specification tool and no path layout, resolves the home through the
  installed binding, and refuses a second home with `spec_home_conflict`.
  `requirements.md`, `design.md`, `tasks.md` and `research.md` are now defined
  as artifact **roles** the binding resolves, so the thirteen authoring rules
  stay correct under every home without being rewritten.
- `spec/openspec` declares the prerequisite the harness cannot install — the
  global OpenSpec CLI, its Node.js floor, `openspec init` and the six generated
  capabilities — and maps EARS logic onto `### Requirement:` / `#### Scenario:`
  with `openspec validate --strict` as the structural gate.
- Remove the remaining tool-named paths from `core/`: `.kiro/` in
  `steering-principles`, and the `.requirements.md` suffix in `bdd-format`.
- New `DOC-G6`: a repository has one populated specification home. `DOC-G2` now
  requires a superseded or deprecated `class: state` document to declare a
  non-empty `superseded_by`; an explicit `[]` records a retirement, a missing
  field records nothing.
- Ship `docs/governance/{docs,skill,stub}-policy.example.json`. The three gates
  previously defaulted to project-owned config the release never provided, so a
  fresh consumer got three executables that failed with a configuration error
  and no documented schema. The copies stay unmanaged (ADR-0009).
- A profile may now carry a `gates/` subtree. The `adr` profile ships
  `scripts/verify-adr.py`, the `ADR-G` gate its skill has been naming as
  `scripts/verify-requirements.sh` — a file that existed in neither the source
  nor any manifest. Section headings and the lesson field are arguments, so the
  gate imposes no natural language (ADR-0009).
- Repair the source workflow: it pinned `v0.1.0-rc.5` against a `v0.2.0-rc.1`
  manifest, so the reproducibility check failed, and it ran only
  `tests/test_harness.py`. CI and the README now discover every test module,
  and `tests/test_release_pins.py` fails offline when a documented pin drifts
  from the manifest version.
- Correct README drift from `v0.2.0-rc.1`: the `select` command and the
  profile families were missing.
- Record that the hosted runner is allocated and the source workflow is green.
  Certification stays `NO-GO`: runner allocation is one of five prerequisites,
  and required-CI branch protection is not among the ones now met.

Consumers of `v0.2.x` receive the specification-home binding only after
reinstalling with a `spec/*` profile; a plain sync with an empty profile list
installs no binding, and `sdd-workflow` then falls back to the home the
repository already populates.

## v0.2.0-rc.1 — 2026-08-03

- Manifest schema 2: profile families (`family/variant`), mutually exclusive
  selection, shared destinations between variants of one family, targets with
  per-target parameter overlays, per-file fan-out, managed roots with
  transactional stray pruning, and `profile_info` menu metadata (ADR-0007).
- `harness.py select`: interactive stack menu rendered entirely from manifest
  data; `--choose family=variant` non-interactive form; `--print-only`;
  `init --reinstall` converges an installed project.
- Move stack content out of core: `io-resilience` ships as
  `transport/nats` / `transport/kafka` variants of one canonical rule path;
  `python-testing-gate` becomes `testing/python-tools` with its foreign
  repository claims neutralized; `adr` becomes the standalone `adr` profile;
  `csharp-fintech` becomes `lang/csharp-fintech`.
- Fix the dangling source pointer in the `karpathy` skill and genericize the
  broker example in `bdd-format`.
- Schema 1 releases install exactly as before; their locks stay byte-identical.

## v0.1.0-rc.8 — 2026-07-29

- Adopt the consumer-born generated-document lifecycle.
- Require generator identity and source digest for every GENERATED document.

## v0.1.0-rc.7 — 2026-07-29

- Record executable mode in release entries and project receipts.
- Apply executable mode transactionally and detect mode-only drift offline.
- Refuse `init --adopt-existing` when content matches but executable mode does
  not.

## v0.1.0-rc.6 — 2026-07-29

- Add lifecycle frontmatter to all fourteen canonical rules so consumer
  metadata ratchets do not increase.
- Distribute generic DOC-G3 stub and SKILL-G boundary verifiers.
- Refuse a new release destination that collides with differing unmanaged
  project content; accept byte-identical target convergence.

## v0.1.0-rc.5 — 2026-07-29

- Accept the second pilot-born BDD clarification: shared Background setup must
  be idempotent.
- Use this release to prove RC4 target-convergence through ordinary `sync`
  without `--force-theirs`.

## v0.1.0-rc.4 — 2026-07-29

- Adopt the pilot-born BDD clarification: Background may contain neither
  assertions nor irreversible mutations, so scenario order cannot affect
  results.
- Let `sync` accept old-lock drift when local bytes already equal the reviewed
  target release, completing the drift → adopt → release → sync loop without
  `--force-theirs`.

## v0.1.0-rc.3 — 2026-07-29

- Make `adopt` patch upstream `origin` paths from the lock instead of consumer
  destinations.
- Record destination-to-origin mappings in adopt metadata.
- Refuse automatic reverse-adoption of rendered templates because the
  project-specific value cannot be generalized safely.

## v0.1.0-rc.2 — 2026-07-29

- Resolve private release assets through the GitHub release API instead of the
  browser download URL, which returns 404 for private assets even with Bearer
  authentication.
- Drop authorization when a signed asset redirect crosses to a storage host.
- Preserve RC status and all RC1 hardening gaps.

## v0.1.0-rc.1 — 2026-07-29

- Establish the core/profile/local ownership boundary.
- Add the stdlib `init`, `sync`, `check`, `diff` and `adopt` CLI.
- Package fourteen canonical rules, six generic skills and the
  `csharp-fintech` two-skill profile.
- Add deterministic manifest/archive generation and reusable receipt CI.
- Mark the release pre-production while private branch protection and tag
  signing remain unavailable.
- Record the hosted-runner billing/spending prerequisite after GitHub refused
  to allocate the initial CI job.
