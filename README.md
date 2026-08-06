# gov-harness

`gov-harness` installs project-neutral working doctrine — rules, skills and
gates — into a target repository, and records a sha256 receipt for every file
it owns. Project truth (ADRs, lessons, requirements, contracts, glossaries)
never crosses a repository boundary; only doctrine does.

## Install

Install **into the target project repository**, not into a home directory and
not into an agent tool's global skills folder. The installed files reference
each other by project-relative paths, so they only work from a project root.

No release tag has been published yet, so the network path cannot be used
today. Clone this repository and install from the clone:

```bash
git clone https://github.com/virusa78/gov-harness ~/src/gov-harness

cd /path/to/your/project
python3 ~/src/gov-harness/harness.py init \
  --project . \
  --source virusa78/gov-harness \
  --to v0.7.0-rc.1 \
  --from-dir ~/src/gov-harness \
  --profile spec/openspec \
  --param golden_sample=requirements/golden.md
```

`--param golden_sample=<path>` is required: it names a project-local artifact
used as the structural example in the EARS rule. Point it at a real file in
your repository.

The profile table below is the whole menu; pick from it and pass `--profile`.
`harness.py select` renders the same menu interactively and prompts in Russian
on stdin — do not run it headless, it will block. Its non-interactive form is
`--choose spec=openspec --choose adr` (repeatable, `family=variant` or a
standalone name), which then runs the install for you.

## What gets installed

Three destinations, three different kinds of content:

```text
<tool-root>/<name>/SKILL.md         skills   — agent capabilities
docs/governance/rules/<name>.md     rules    — doctrine the skills read
scripts/<name>.py|.sh               gates    — executable checks
.harness.lock                       receipt  — version, digests, selection
```

A minimal install (`--profile spec/openspec`) produces exactly this:

```text
.agents/skills/     karpathy, sdd-workflow, shell-testing-gate, truth-pipeline
.claude/skills/     the same four
.codex/skills/      the same four
docs/governance/    rules/ (14 files incl. spec-home.md), 3 *-policy.example.json
scripts/            harness.py, governance_docs.py, verify-docs.sh,
                    verify-skills.py, sync-agent-stubs.py
.harness.lock
```

## Agent tool roots

Skills install into every declared target root, so each tool finds them in the
place it already looks:

| Target | Root | Read by |
|---|---|---|
| `agents` | `.agents/skills/` | tool-neutral convention |
| `claude` | `.claude/skills/` | Claude Code, project scope |
| `codex` | `.codex/skills/` | Codex CLI, project scope |

All three are installed by default. To pick a subset, pass `--target` on
`init` (repeatable); the choice is recorded in `.harness.lock` and honoured by
later syncs:

```bash
python3 ~/src/gov-harness/harness.py init --project . ... --target codex
```

Every target root is a **managed root**: a file inside one that the receipt
does not own is reported by `check` as a stray and pruned on
`init --reinstall`. Hand-copying a skill into any of them is detected.

Install into the project, never into `~/.codex/skills/` or `~/.claude/skills/`.
Personal machine-level directories cannot carry a receipt and cannot see the
project-local rules that the skills read.

**Skills and rules are not the same thing.** A skill is a capability an agent
loads; a rule is doctrine a skill reads. Most of what this release ships is
rules. In particular:

> The OpenSpec binding is a **rule**, `docs/governance/rules/spec-home.md`.
> It is not a skill and will never appear in a list of installed skills.
> `sdd-workflow` reads it to learn where requirement truth lives.

## Choosing profiles

`core/` is always installed. Profiles are optional. Within a family the
variants are mutually exclusive — selecting two of them is refused.

| Family | Variants | Pick when |
|---|---|---|
| `spec` | `openspec`, `kiro`, `plain` | always — it decides where requirement truth lives |
| `transport` | `nats`, `kafka` | the project consumes a message broker |
| `lang` | `csharp-fintech` | C# financial backend |
| `testing` | `python-tools` | the project writes Python verification scripts |
| — | `adr` | the project keeps `docs/architecture/decisions/` |
| — | `workflow/superpowers` | you want the git-worktree, subagent and code-review workflow |

## Vendored content

`workflow/superpowers` ships six skills vendored from
[obra/superpowers](https://github.com/obra/superpowers) at a pinned commit,
under MIT. They arrive inside the release archive under the same receipt as
everything else — **the installer never contacts an upstream**, so there are no
live updates and no surprise changes (ADR-0011).

```text
dispatching-parallel-agents     finishing-a-development-branch
receiving-code-review           requesting-code-review
subagent-driven-development     using-git-worktrees
```

The set is closed under the upstream's cross-skill references, so no shipped
file points at a capability you do not receive. The upstream addresses siblings
through its plugin namespace; that prefix is rewritten to the bare skill name,
because the namespace does not exist in a plain install. The rewrite is
recorded — the manifest carries both the shipped digest and the upstream
digest, and they differ exactly where a patch exists.

**Overlap you should know about.** `requesting-code-review` and
`receiving-code-review` describe a generic review workflow; the
`lang/csharp-fintech` profile ships a C#-specific review *checklist*. They
compose — one is process, the other is content. Nothing here competes with
`sdd-workflow` for the planning lifecycle: the upstream's planning skills
(`writing-plans`, `executing-plans`, `test-driven-development`,
`verification-before-completion`) are deliberately **not** vendored, because a
second owner of that lifecycle is the defect ADR-0008 removed.

The upstream licence installs to `docs/governance/licenses/`. To move to a
newer upstream commit, a maintainer runs `scripts/vendor_upstream.py fetch`
in this repository and the change lands as an ordinary reviewed diff.

`spec/openspec` needs a prerequisite the harness cannot install:

```bash
npm install -g @fission-ai/openspec@latest   # Node.js 20.19.0+
cd /path/to/your/project && openspec init
```

That generates six capabilities — propose, explore, apply, update, sync,
archive. If the CLI is missing, the binding reports a prerequisite gap rather
than falling back to another layout, because a silent fallback is how a
repository grows a second home of truth. See ADR-0008.

## Reaching tools that do not load skills

Most agent tools read `AGENTS.md` rather than a skill directory. The gate
splices a generated section into yours, leaving every other byte alone:

```bash
python3 scripts/sync-agent-stubs.py --root . --write   # create or refresh
python3 scripts/sync-agent-stubs.py --root .           # exit 2 if stale
```

The block holds **pointers, not doctrine** — it names where the rules live and
the single-specification-home invariant, and stops there. A copy of the rules
in a file every tool reads on every task would be the copy that rots. Edits
outside the markers are yours and never reported. Remove `agents_file` from
`stub-policy.json` to opt out entirely. See ADR-0013.

## Verifying the release signature

Without a key, `harness.py` checks the archive against a `SHA256SUMS` served by
the same host — that proves the download was not corrupted, not that the
release is genuine. Pass the publisher's public key and the check becomes
authenticity:

```bash
python3 ~/src/gov-harness/harness.py init --project . ... \
  --public-key /path/to/gov-harness-release.pub.pem
```

The key is **yours**, obtained out of band, and never travels inside the
release — a key shipped by the thing it authenticates proves nothing. The path
is recorded in `.harness.lock`, so later syncs keep demanding a valid signature
without repeating the flag. With a key configured, a missing signature, an
invalid one, a missing key file, or an unusable `openssl` each refuse the
install. Requires `openssl`; `--from-dir` installs are unsigned by construction
and record no key. See ADR-0012.

Cutting a signed release:

```bash
python3 scripts/package_release.py --version <tag> --sign-key /path/to/private.pem
# emits dist/SHA256SUMS.sig alongside the archive; attach all three
```

Note: signing is opt-in and **this repository publishes no key yet**, so
current releases are unsigned. `docs/HARDENING.md` tracks it.

## Configure the gates

The shipped gates read project-owned policy files. Copy the examples once and
edit them; the copies are unmanaged, so your edits are configuration and not
receipt drift.

```bash
cd docs/governance
for name in docs skill stub; do cp "$name-policy.example.json" "$name-policy.json"; done
```

Each example documents its own schema in an `_about` field the gates ignore.
`docs-policy.json` is where you declare `spec_home`, which `DOC-G6` enforces:
one populated specification home, and every absorbed document naming its new
owner in `superseded_by`.

## Verify and update

```bash
python3 scripts/harness.py check      # receipt integrity and strays
python3 scripts/governance_docs.py --root . --mode block
python3 scripts/verify-skills.py --root .
```

Exit codes are not uniform across the tools — key off the right column:

| Command | clean | findings | config error |
|---|---|---|---|
| `harness.py check` / `diff` | 0 | 2 (drift or strays) | 3 (integrity or refusal) |
| `governance_docs.py --mode block` | 0 | 1 | 2 |
| `verify-skills.py` | 0 | 2 | 2 |
| `sync-agent-stubs.py` | 0 | 2 | 2 |
| `verify-adr.py` (adr profile) | 0 | 2 | 2 |

Without `--mode block`, `governance_docs.py` reports findings and still exits
0; use `block` in CI.

Updates name a tag explicitly — there is no `latest` — and should land through
a dedicated review:

```bash
python3 scripts/harness.py sync --to <tag>
```

To change the selection later, re-run `select --reinstall` (repeat `--param`;
it is not read back from the lock).

## Do not do these

| Wrong | Why it breaks |
|---|---|
| Copying `core/skills/` or `profiles/` by hand | No `.harness.lock`, so no receipt and no drift detection. `SKILL-G` exists to catch exactly this. |
| Installing into `~/.codex/skills/`, `~/.claude/skills/` or any global folder | Rule links inside a skill resolve project-relative. From a home directory they point at paths that do not exist, so every rule reference dangles. |
| Installing skills globally and expecting the OpenSpec binding to apply | The binding is a project-local rule. A globally installed skill can never see it. |
| Editing an installed file in place | `check` reports it as drift. Use `adopt` to send the change upstream, or an `--override` to claim local ownership. |

Adding a tool whose skill root is not two path segments deep (`.agents/skills`
is two) is not currently possible: a skill links its rules as
`../../../docs/governance/rules/…`, which only lands on the project root from a
two-segment root. See ADR-0010.

## Working on this repository

For contributors to `gov-harness` itself, not for consumers:

```bash
python3 -m unittest discover -v -t . -s tests -p "test_*.py"
python3 scripts/verify_source.py
python3 scripts/build_manifest.py --version v0.7.0-rc.1 --check
```

Read `docs/INDEX.md` first. A rule, gate, manifest schema, ownership boundary
or release behavior change needs an ADR and a CHANGELOG entry in the same
commit.

## Release status

All `-rc.*` versions are pre-production. Production certification is `NO-GO`:
of the five promotion prerequisites only hosted-runner allocation is met.
Protected `main` with required CI, CODEOWNERS enforcement, signed tags and a
clean external pilot remain open. See `docs/HARDENING.md`.
