# Governance index

- [ADR index](architecture/decisions/README.md)
- [Hardening status](HARDENING.md)
- [Release history](../CHANGELOG.md)
- `core/rules/` — the only stack-neutral rule home (13 rules)
- `core/skills/` — four project-neutral skills
- `core/gates/` — the shipped document, stub and skill gates
- `core/policies/` — example configuration a consumer copies and owns (ADR-0009)
- `profiles/spec/{openspec,kiro,plain}/rules/` — exclusive specification-home
  bindings, one canonical `spec-home` rule (ADR-0008)
- `profiles/transport/{nats,kafka}/rules/` — exclusive variants of `io-resilience`
- `profiles/lang/csharp-fintech/skills/` — two optional C# financial-backend skills
- `profiles/testing/python-tools/skills/` — Python verification-script discipline
- `profiles/adr/` — opt-in ADR workflow and its `ADR-G` gate
- `release/manifest.json` — generated release source map (schema 2, ADR-0007)

