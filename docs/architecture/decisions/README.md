# Architecture Decision Records

## Index

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](0001-versioned-receipt-distribution.md) | Distribute governance through a versioned receipt, never project-to-project copies | Accepted |
| [ADR-0002](0002-adopted-target-bytes-are-explained-drift.md) | A reviewed target release explains matching local drift during sync | Accepted |
| [ADR-0003](0003-bdd-background-setup-is-idempotent.md) | BDD Background setup is idempotent and scenario-order independent | Accepted |
| [ADR-0004](0004-release-growth-cannot-overwrite-unmanaged-paths.md) | Release growth cannot silently overwrite unmanaged paths | Accepted |
| [ADR-0005](0005-receipts-cover-executable-mode.md) | Receipt integrity includes executable mode | Accepted |
| [ADR-0006](0006-generated-documents-have-distinct-lifecycle.md) | Generated documents have a distinct lifecycle | Accepted |
| [ADR-0007](0007-stack-content-lives-in-exclusive-profile-families.md) | Stack content lives in mutually exclusive profile families; the menu is manifest data | Accepted |
| [ADR-0008](0008-specification-home-is-an-exclusive-profile-axis.md) | One specification home per repository, selected as an exclusive profile axis; OpenSpec wins when present | Accepted |
| [ADR-0009](0009-a-profile-ships-the-gate-its-skill-names.md) | A profile ships the gate its skill names; consumer config ships as an example | Accepted |
| [ADR-0010](0010-skills-fan-out-into-declared-tool-roots.md) | Skills fan out into declared agent tool roots; every root is managed and two segments deep | Accepted |
| [ADR-0011](0011-the-harness-governs-content-it-did-not-author.md) | Foreign content is vendored and pinned by static composition; the installer never fetches from an upstream | Accepted |
| [ADR-0012](0012-the-release-is-signed-and-the-key-comes-from-the-consumer.md) | The release is signed; the verifying key is supplied by the consumer, never by the release | Accepted |
| [ADR-0013](0013-doctrine-is-visible-through-a-generated-agents-md-block.md) | Doctrine reaches non-skill tools through a generated block inside the consumer's AGENTS.md | Accepted |
| [ADR-0014](0014-a-completion-claim-is-a-record-that-goes-stale.md) | A completion claim is a recorded command bound to a commit; it expires when the code changes | Accepted |
| [ADR-0015](0015-a-source-is-validated-where-it-is-recorded.md) | The source is validated and normalized at install; both spellings resolve so existing locks keep working | Accepted |
| [ADR-0016](0016-an-unconfigured-gate-skips-and-says-so.md) | Absence of the thing a gate governs is an announced skip, not a failure; an explicit path is still asserted | Accepted |
| [ADR-0017](0017-a-project-owned-policy-is-compared-to-the-example-it-came-from.md) | A policy copy must account for every key its example defines; declining is explicit, not knowing is a finding | Accepted |
