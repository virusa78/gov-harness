# gov-harness

`gov-harness` distributes project-neutral working doctrine with a verifiable
receipt. Project truth—ADRs, lessons, requirements, contracts, registries,
glossaries and intake—never crosses repository boundaries.

The release has three ownership layers:

- `core/`: invariant rules, generic skills, gates and the distribution CLI;
- `profiles/`: optional stack policy in mutually exclusive families
  (`transport/*`, `lang/*`, `testing/*`) plus standalone toggles (`adr`);
- `local/`: project-owned configuration and component-specific rules, never
  modified by sync.

The one-file stdlib CLI exposes:

```text
harness.py init / select / sync / check / diff / adopt
```

Every install creates `.harness.lock` with a pinned version, release digest,
profiles, parameters, overrides and a sha256 receipt for every managed file.
There is no `latest`; updates name a tag explicitly and should land through a
dedicated review.

## Specification home

A consumer selects where present-tense requirement truth lives the same way it
selects a transport: `spec/openspec`, `spec/kiro` and `spec/plain` are mutually
exclusive variants of one family and share the canonical rule path
`docs/governance/rules/spec-home.md`, so switching swaps the binding in place.

`core/` holds the lifecycle and names no layout. `spec/openspec` additionally
declares a prerequisite the harness cannot install — the global OpenSpec CLI —
because a binding that silently degrades to another layout when its tool is
absent is how a repository grows a second home of truth. See ADR-0008.

## Consumer configuration

The shipped gates read project-owned policy files. Copy the examples once and
edit them; the copies are unmanaged, so your edits are configuration and not
receipt drift.

```bash
cd docs/governance
for name in docs skill stub; do cp "$name-policy.example.json" "$name-policy.json"; done
```

Each example documents its own schema in an `_about` field the gates ignore.
`docs-policy.json` is where a repository declares `spec_home`, which `DOC-G6`
enforces: one populated specification home, and every absorbed document naming
its new owner in `superseded_by`.

## Local verification

```bash
python3 -m unittest discover -v -t . -s tests -p "test_*.py"
python3 scripts/verify_source.py
python3 scripts/build_manifest.py --version v0.3.0-rc.1 --check
```

## Release status

All `-rc.*` tags are pre-production. Until private `main` protection and
signed tags are available, production certification is explicitly `NO-GO`;
see `docs/HARDENING.md`.
