# Governance index

- [ADR index](architecture/decisions/README.md)
- [Hardening status](HARDENING.md)
- [Release history](../CHANGELOG.md)
- `core/rules/` — the only stack-neutral rule home (13 rules)
- `core/skills/` — four project-neutral skills
- `profiles/transport/{nats,kafka}/rules/` — exclusive variants of `io-resilience`
- `profiles/lang/csharp-fintech/skills/` — two optional C# financial-backend skills
- `profiles/testing/python-tools/skills/` — Python verification-script discipline
- `profiles/adr/skills/` — opt-in ADR workflow
- `release/manifest.json` — generated release source map (schema 2, ADR-0007)

