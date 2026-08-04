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

## Local verification

```bash
python3 -m unittest discover -v -t . -s tests -p "test_*.py"
python3 scripts/verify_source.py
python3 scripts/build_manifest.py --version v0.2.0-rc.1 --check
```

## Release status

All `-rc.*` tags are pre-production. Until private `main` protection and
signed tags are available, production certification is explicitly `NO-GO`;
see `docs/HARDENING.md`.
