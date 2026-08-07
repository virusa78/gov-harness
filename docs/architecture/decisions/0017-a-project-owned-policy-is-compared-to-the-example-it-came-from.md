# ADR-0017: A project-owned policy is compared to the example it came from

## Status

Accepted — 2026-08-07

## Context

Every gate here is configured by a file the project owns. The consumer copies
`X.example.json` once, edits it, and the harness never touches the copy again.
That ownership is deliberate and it is right: the alternative is an installer
that overwrites the consumer's configuration on every sync.

It has a failure mode nobody was watching.

When a release adds a capability, it adds a key to the *example*. The *copy*,
being project-owned, does not gain it. The gate reading the copy sees no key,
treats the capability as unconfigured, and reports clean. Nothing anywhere
tells the project that something shipped.

The pilot made this concrete. Migrating it from `v0.5.0-rc.1` to `v0.9.0-rc.1`
succeeded, `check` reported clean, every gate was green — and:

```
POLICY-G stub-policy.json: the example defines 'agents_file' ...
POLICY-G docs-policy.json: the example defines 'evidence_journal' ...
POLICY-G docs-policy.json: the example defines 'requirement_pattern' ...
POLICY-G docs-policy.json: the example defines 'requirements_source' ...
```

Four capabilities delivered across four versions and never adopted. `AGENTS.md`
was never generated because `agents_file` was not in the copy. `EVID-G` — the
gate this project built specifically so that completion claims become records —
was installed, ran on every commit, and printed a cheerful
`SKIP EVID-G: ... not configured` every time.

That SKIP was correct, and it was the sound of the whole evidence subsystem
being inert. Nobody could have known from the output.

This is worse than the defects in ADR-0015 and ADR-0016, because neither of
those is silent. A late refusal is still a refusal; a red gate is still red.
This one is green all the way down.

## Decision

**A policy copy must account for every key its example defines. Not adopt —
account for.**

`POLICY-G` (`scripts/verify-policies.py`) pairs each `X.example.json` with
`X.json` and reports:

- a key the example defines that the copy neither carries nor declines;
- a key the copy carries that the example does not define (a typo, or a key a
  release removed);
- a `schema_version` gap.

The escape is explicit rather than absent: a project declines a key by naming
it in `_declined`. Keys beginning with `_` were already ignored by every policy
loader, so this needs no schema change and no gate rewrite.

**Declining is a decision and leaves a trace; not knowing is neither.** That is
the entire point. The gate does not have an opinion about whether a project
should use `agents_file`. It has an opinion about whether the project has ever
been in a position to choose.

Two further rules keep it from crying wolf, because a gate that cries wolf gets
switched off and then protects nothing:

- an example with no copy is not a finding — not adopting a gate is a
  legitimate state, and the gate itself already says "copy the example" when
  asked to run;
- a stale `_declined` entry, naming a key the example no longer defines, is a
  finding, so the declination list cannot silently accumulate names of things
  that no longer exist.

## Consequences

Upgrading now surfaces what the upgrade brought. A consumer syncing across
several versions gets a list of the capabilities they have not been told about,
and must either configure them or say, in the file, that they do not want them.

Existing projects will fail POLICY-G the first time they run it. That is the
correct outcome and not a migration burden imposed by this decision — it is the
backlog that was already there, made visible. The pilot's four findings existed
before the gate did.

Malformed JSON in a policy copy is a configuration error (exit 3), not a pass.
The distinction between "I checked and it is fine" and "I could not check"
appears in the exit code, as it does in `check_branch_protection.py`.
