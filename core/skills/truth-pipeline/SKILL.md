---
name: truth-pipeline
description: Minimal spec-driven "single source of truth" discipline plus a shadow-migration protocol for safely replacing a working system. Use this skill whenever the user wants to set up spec/ + tasks/ repositories, seal completed tasks, enforce spec-sync CI tripwires, run a shadow rollout with a tribunal log (append-only JSONL), compute a clean-wave window before flipping to a new implementation, or asks about "truth pipeline", spec-driven development, sealed tasks, shadow mode, divergence tribunals, flip/rollback gates, or migrating truth out of stale docs and tasks — even if they don't use these exact terms.
---

# Truth Pipeline — Absolute Minimum

A discipline for keeping one living source of truth and safely migrating working
mechanisms. Toolchain: git, sha256sum, diff/patch, JSONL, one blocking CI lint,
one Python window-report script. No framework needed — a framework instead of
discipline is buying a gym membership instead of doing squats.

**Core in one line:** Truth lives in one document, speaks in the present tense,
every line carries provenance, and a gate guards it. Everything else is an
event: dated, sealed, visible, but never resurrected.

## Scope of applicability

This certifies a *mode*, not a distribution.

- **Works as-is:** single writer or small team, greenfield or small codebase,
  one operator loop, normal deadline pressure, git as history.
- **Needs hardening:** 5–15 people / multiple reviewers, legacy backlogs,
  multiple agents, politically contested PRs. Add: code owners on `spec/`,
  mandatory review for sealed-task changes, protected branches, signed commits
  or another tamper-evident journal, a separate adjudicator for tribunal calls.
- **Not certified:** 50+ people without spec code owners, conflicting roadmaps
  across teams, regulated audits without signatures/immutable logs, hostile
  repos where participants deliberately forge history.

Greenfield adopts in a day. Legacy migration cost may be unbounded — do not
call it small until you've measured it.

## Two document types (there are no others)

```text
spec/   STATE.  Current truth. Editable. The present tense belongs to it.
tasks/  EVENTS. Intent + delta + acceptance criteria. After merge: sealed/read-only.
```

Four rules — break any one and you fork the truth:

1. **A task never retells the system.** A task = a reference to spec sections,
   `was → becomes`, acceptance criteria. Retelling inside a task is a second
   head of truth, and it rots first. Need a quote? Pin `spec@<hash>`.
2. **Definition of Done is transactional:** the spec patch ships in the *same
   PR* as the code. No spec patch when truth changed → task is not closed.
3. **A closed task is sealed machine-readably:** `status: sealed`,
   `truth_as_of: <commit>`, `superseded_by: [...]`. Prose headers don't count —
   an agent will eat prose, but it must respect the field.
4. **A spec line without provenance** (anchor to code/test/measurement + date)
   **is posturing.** Cut it without mercy. Not one number pulled from thin air.

## Lints and gates: tiers, not amulets

A minimal lint does not prove text is true; it catches forgetfulness. Call it
honestly: a **tripwire**, not a verifier.

```text
tier 1: tripwire         PR closing a task with spec_refs → those §§ must change
                         in the same diff. Catches: forgot to update spec.
                         Misses: a whitespace edit posing as a real update.
tier 2: semantic review  Reviewer confirms was/becomes reflected, acceptance
                         green, provenance present, old text not resurrected.
tier 3: structured spec  §§ have id, provenance, owner, updated_at,
                         evidence_ref; diffs checked by a parser, not grep ritual.
tier 4: adversarial gate independent probes derived from claims, poison corpus,
                         replay, tamper checks. Catches not everything — but bites.
```

Absolute minimum = tier 1 as a blocker + tier 2 in review. Never sell tier 1
as a verifier — it's a doorbell, not a forensic examiner.

## Truth migration protocol (replacing a working mechanism)

### Stage 0 — Don't shout, measure
A hole found on synthetic input is a `code_fact`, not a fire. Run it against a
live corpus. Threat status has three axes:

```text
existence:  code_fact -> synthetic_repro -> real_observed
activation: unmeasured | inactive | active | recurring
class:      drift | attack | control_plane | transmission
```

Iron law: **unmeasured is never "inactive."** Second law: zero attacks on a
benign corpus proves almost nothing — the first observed attack is often the
exploit. Drift can be demoted with a zero on live data; attack-class is only
demoted by a cheap invariant installed *now*.

### Stage 1 — FREEZE
Debate to saturation. When edits become about wording rather than landmines,
the text freezes: sha256, changelog, work queue. From then on truth is mined
in the substrate, not in round seven of debate. A seal without a hash is a mood.

### Stage 2 — Sentinel before scalpel
First a read-only sensor wired to the preconditions of every known landmine.
Key variable split:

```text
regime — must be STABLE: brief template, policy, parser versions.
         Regime drift = assurance void: calibration is dead, re-certify.
wave   — must CHANGE: target, roster, snapshot.
         A verdict pins to its wave. Mismatch at use time = STALE.
```

Mix the axes up and the sensor eats itself: either a perpetual void from every
new task, or blindness to regime drift.

### Stage 3 — Shadow
**New computes, old decides.** Both paths run on the same wave. The old path
stays authoritative; the new path emits telemetry. Divergence = alert in the
journal, never a flip. Shadow is the *default*, not a flag — a forgotten flag
must not be able to silently skip the window.

### Stage 4 — Tribunal
Append-only JSONL. The executor may only write:

```json
{"type":"classification","divergence_id":"D-123","disposition":"pending","root_cause":"unknown"}
```

The executor never self-classifies its own divergences — otherwise it's a
laundromat: dirty error in, clean explanation out. Classification is a separate
record; the last valid record wins. Report semantics:

```text
clean wave     = measured AND (matched OR all its divergences excused)
excused        = only by record: sentinel_bug + replay green,
                 or a pre-declared, signed delta-class
unknown        = resets the window
pending        = resets the window
not measured   = doesn't count AND doesn't reset (a crashed run isn't a wave)
corrupt line   = window cannot be certified at all: fail-closed
not recorded   = does not exist
```

**Solo mode** (so one person isn't judge and defendant in the same mask):
executor pass writes waves/divergences as unknown/pending with no excuses;
adjudicator pass is a separate commit with replay evidence and
`solo_review: true` in the record. Forbidden: creating a divergence and
excusing it in the same pass. Assurance is lower — say so. For 50 people you
need a real separate adjudicator.

### Stage 5 — Window and flip
Flip is licensed only after:

```text
N clean waves in a row (trailing streak — a dead streak does not resurrect)
N recorded BEFORE the window starts (never chosen after peeking at the counter)
poison corpus green
declared delta-classes signed
zero unresolved tamper
tribunal report = SATISFIED
```

Flip = one config line + a journal record. Rollback = a second line. The old
mode stays alive as a lever. If the flip feels heroic, the scheme broke earlier.

### Stage 6 — RC-format delivery
Ship: patch, EVIDENCE.md, sha256 seals, apply-proof (reverse → forward
roundtrip, byte-clean), independent probes written from the claims (not traced
off the tests), and an **honest boundary** — what's stubbed, what's a capsule,
what's production. Whoever didn't name the boundary hid it.

## Reference implementation

`scripts/tribunal_report.py` is the copy-paste skeleton: reads the JSONL,
validates records, keeps last classifications, replays waves, prints
`SATISFIED`/`UNSATISFIED`; a corrupt journal kills the process (`FAIL_CLOSED`,
exit 3). Read it before wiring the journal — it fixes the window semantics and
makes fail-closed cheaper than self-deception. It does NOT replace tamper-proof
storage, signatures, code owners, or review.

Journal format:

```jsonl
{"type":"window_config","n":20,"poison_green":true,"deltas_signed":true}
{"type":"wave","wave_id":"W-001","measured":true,"matched":false,"divergences":["D-1"],"tamper_unresolved":false}
{"type":"classification","divergence_id":"D-1","disposition":"excused","excuse_kind":"sentinel_bug","replay":"green"}
{"type":"wave","wave_id":"W-002","measured":true,"matched":true,"divergences":[],"tamper_unresolved":false}
```

## Adoption

**Greenfield (day one):**
1. `mkdir -p spec tasks`
2. Task frontmatter template: `status: open`, `spec_refs: []`, `truth_as_of:`,
   `superseded_by: []`
3. Tier-1 CI tripwire: a PR closing a task with `spec_refs` must change those
   sections in the same diff.
4. Add `.tribunal.jsonl` + `tribunal_report.py`.
5. For a risky replacement, enable shadow as the default; record
   `window_config` before the first wave.
6. Ship only in RC format (patch, EVIDENCE, sha256, roundtrip, probes, honest
   boundary).

**Legacy (no "one day" fairy tale):**
1. Inventory all truth sources (docs, tasks, comments, tests, runbooks, wiki).
2. Extract the *live* truth that actually governs behavior.
3. Mine it into `spec/` once, with provenance and dates.
4. Stamp old tasks as events (`sealed`, `truth_as_of`, `superseded_by`) — never
   rewrite them; history isn't cured by a facelift.
5. Only after migration enable the gate; before it, the gate either screams or
   lies.

## Laws for the wall

```text
 1. The present tense belongs to spec/.
 2. Unrecorded = a number from thin air.
 3. Unmeasured ≠ inactive.
 4. The dead are visible but do not resurrect.
 5. New computes, old decides, until the window closes.
 6. Divergence = alert, not flip.
 7. The executor does not judge itself: unknown + pending.
 8. A requirement lives as a default, not a flag.
 9. Flag or amendment. There is no third option.
10. Amendments are signed before deploy. Backdating = laundering.
11. History is stamped, not rewritten.
12. Gate, not discipline. Discipline dies at the first deadline.
13. Never call a tripwire a verifier.
14. Never call solo mode an independent tribunal.
15. A document with no external reproduction proves no transmission.
```

## Anti-patterns

A "truth-status" spec without transactions and a gate (a rotten spec is worse
than none — nobody believes a missing one). `explained` without a journal
record. Self-classifying your own divergences. Flipping on "we're confident
anyway" with paperwork backdated. Rewriting old tasks instead of stamping them.
Demoting attack-class with a zero on a benign corpus. Choosing N after looking
at the counter. Flipping on a historical best streak while a live divergence
sits in the tail. Tier-1 grep sold as proof of meaning. A solo operator who, in
one commit, created a divergence, excused it, and awarded themselves a medal.

## Honest status boundary

The scheme has proven *existence* in one mode (single-writer, small codebase,
one gate, operator+agent, no politics): real gate run, 115/115 tests, 12/12
external probes, byte-clean patch roundtrip, shadow living as default, N=20
recorded before the window. **Transmission is unmeasured** until an external
operator reproduces it and leaves a trail (repo/commits, input corpus, tribunal
log, window report, patch roundtrip, notes on what was confusing). Record each
external reproduction in `EVIDENCE.md` (operator, date, repo, commits
before/after, mode, tribunal report, roundtrip, probe counts, required text
changes, operator notes). Anything unrecorded does not exist.

## Done criterion

The reader can: create `spec/` and `tasks/`; seal an old task; catch a missing
spec update with the tripwire; create `.tribunal.jsonl`; run
`tribunal_report.py`; get UNSATISFIED before the window and SATISFIED after N
clean waves; and explain why none of this proves transmission without an
external run.
