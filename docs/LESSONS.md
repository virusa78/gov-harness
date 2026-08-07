# Lessons

## L1 — Private release assets are API resources, not authenticated browser URLs (2026-07-29)

Symptom: the first real network `init` received 404 from a private GitHub
release asset even though the request carried a valid Bearer token; local
`--from-dir` tests had all passed.

Cause: private release downloads require resolving the release asset through
the GitHub API and requesting the asset API URL with
`application/octet-stream`. Adding authorization to the public browser URL
does not turn it into the private API flow.

Rule: every private-release transport must be tested from outside the source
checkout and must resolve an asset ID through the provider API; local archive
tests do not prove authenticated distribution. Remove authorization on a
redirect to a different storage host.

Source: `v0.1.0-rc.1` network-init reproduction and ADR-0001.

## L2 — Adopt patches upstream origins, not consumer destinations (2026-07-29)

Symptom: an installed rule lives at `docs/governance/rules/...`, while its
upstream source lives at `core/rules/...`; a patch named with the installed
path cannot be applied to upstream.

Cause: the first implementation treated the visible project path as source
identity even though `.harness.lock` already carried the actual `origin`.

Rule: reverse-flow artifacts use lock origin paths and record an explicit
destination-to-origin mapping. Rendered templates are refused because a tool
cannot infer which part of a local value should become a generic parameter.

Source: pre-pilot full-loop review, `v0.1.0-rc.2`, ADR-0001.

## L3 — Old-lock drift can already be the reviewed target (2026-07-29)

Symptom: after a pilot improvement was accepted upstream, ordinary sync would
still refuse because it compared local bytes only with the old lock.

Cause: drift classification happened before the target release was available,
so the tool could not distinguish an unexplained edit from already-converged
reviewed bytes.

Rule: sync refusal compares local bytes with both the old receipt and the
integrity-validated target; exact target bytes are explained, everything else
still fails closed.

Source: persistent pilot adopt loop, ADR-0002.

## L4 — A mechanism nobody exercises is not a feature (2026-08-06)

Symptom: an audit found the same defect eight times in one pass. Fan-out
targets were built and never declared, so `.agents/skills` was the only skill
root. `ADR-G` was named by a skill as a shipped gate and the file existed
nowhere. Three gates defaulted to policy files the release never shipped and
never documented. CI pinned `v0.1.0-rc.5` against a `v0.2.0-rc.1` manifest, so
the reproducibility check would have failed on any run. `core/` named Kiro and
cc-sdd while `AGENTS.md` forbade exactly that. `DOC-G2` accepted
`status: superseded` without asking what superseded it. No `AGENTS.md` was
shipped to consumers although a stub generator sat ready. None of it was
visible to any check that existed.

Cause: verification was structural rather than behavioural. `verify_source.py`
compares inventories against hardcoded sets, and the unit suite exercises
units; neither runs the loop a consumer runs. Every one of those defects is
invisible to an inventory comparison and obvious within seconds of an actual
install. The one control that would have caught the version drift — hosted CI —
was the control that was never funded, so a repository whose own doctrine says
"gate, not discipline" ran on discipline for four releases. And the ADRs were
written in the permissive mood: ADR-0007 said the manifest *may* declare
targets, nothing asked whether it did, and so nothing ever did.

Rule: a capability the release format supports must be exercised by the release
or explicitly recorded as unused, and every ADR states its implementation
status; a test that installs into a scratch project and runs the shipped gates
is mandatory for any change to the release format.

Source: v0.3.0-rc.1 and v0.4.0-rc.1 audit; ADR-0008, ADR-0009, ADR-0010.

## L5 — A green check on an inert subsystem is worse than a red one (2026-08-07)

Symptom: the pilot migrated from `v0.5.0-rc.1` to `v0.9.0-rc.1`, `check`
reported clean, all seven gates passed, and four capabilities shipped across
those four versions were sitting unused. No `AGENTS.md` had ever been
generated. `EVID-G` — built precisely so that a completion claim becomes a
record — ran on every invocation and printed `SKIP EVID-G: ... not configured`,
which was true, correct, and indistinguishable from working.

Cause: the three gate configurations are project-owned files, copied once from
a shipped example and never touched again by design. When a release adds a
capability it adds a key to the example; the copy does not gain it; the gate
reads the copy, finds nothing, and reports what it honestly found. Every layer
behaved correctly and the composition told the consumer nothing. The same pass
found two quieter versions of the same shape: an install-time defect that only
announced itself at the first network sync months later (ADR-0015), and a gate
that was red on day one for a project that had done nothing wrong, which trains
a reader that red is the normal colour (ADR-0016).

Rule: whenever the harness ships something a project must opt into, the release
must also ship the comparison that makes not opting in visible; "not
configured" and "configured and satisfied" must never share an exit code or a
line of output, and declining a capability must be an explicit statement in the
consumer's own file rather than an absence.

Source: v0.9.0-rc.1 pilot verification; ADR-0015, ADR-0016, ADR-0017.
