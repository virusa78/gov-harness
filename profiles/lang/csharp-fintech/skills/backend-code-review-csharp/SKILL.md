---
name: backend-code-review-csharp
description: Deterministic backend code review checklists for C# REST API, Redpanda/Kafka, PostgreSQL, Redis. 16-section Done/Not Done review system for financially material workflows. Idempotency, outbox/inbox, ordering, source-of-truth discipline.
license: MIT
metadata:
  category: code-review
  complexity: advanced
  author: gov-harness
  version: 1.0
---

## Spec-Driven Protocol (mandatory)

This skill operates within the SDD framework. When reviewing code:
- Map every finding to a requirement ID from the Requirement Matrix
- Classify each requirement by **EARS type**: Ubiquitous, Event-Driven, Unwanted Behaviour, State-Driven, Optional Feature, Complex
- Reference the EARS type in your review notes
- Flag missing EARS classification as an SDD protocol gap

The target repository's declared SDD protocol remains authoritative for phase
order and evidence locations.



# C# Fintech Backend Code Review Checklists
## Done / Not Done Review System
### Version 1.0
### Scope: C#, REST API, Redpanda/Kafka-compatible messaging, PostgreSQL, Redis

Purpose: turn backend review from “build passes” into a deterministic acceptance system for an operator-critical financial platform.

This document assumes:
- PostgreSQL is transactional source of truth
- Redpanda/Kafka-compatible broker is durable async bus, not source of truth
- Redis is cache/locks/rate-limits/hot ephemeral state only
- outbox/inbox are mandatory
- business ordering is aggregate_sequence, not broker-wide ordering
- material corrections are append-only, not destructive overwrite

---

# 1. Why this exists

Normal backend review often fails in financial systems because reviewers ask:

- “compiles?”
- “tests green?”
- “endpoint returns 200?”
- “consumer runs?”

That is too weak.

For an operator-critical financial backend, review must answer:

- is this safe for financially material workflows?
- is idempotency real or assumed?
- is the DB still the source of truth?
- can the service recover after partial failure?
- is ordering explicit?
- are destructive writes prevented?
- can operators investigate and replay failures?

So every important backend unit gets a **Done / Not Done** checklist.

If a mandatory item is “Not Done”, the review result is “Not Done”.

---

# 2. Review model

Each reviewable unit is checked at 6 levels:

1. Architecture
2. API / contract quality
3. Data integrity
4. Messaging / async correctness
5. Failure handling / operability
6. Engineering quality

Each item is marked:

- Done
- Not Done
- N/A

Mandatory items cannot be waived casually.

---

# 3. Global review gates

These gates apply to every backend pull request.

## 3.1 Global Gate A — Architecture
- [ ] Done / Not Done — Service ownership boundaries remain clear
- [ ] Done / Not Done — No service writes directly into another service’s owned tables
- [ ] Done / Not Done — PostgreSQL remains source of truth for business facts
- [ ] Done / Not Done — Redis is not used as source of truth
- [ ] Done / Not Done — Message broker is not treated as canonical state store
- [ ] Done / Not Done — Shared building blocks are reused instead of copy-paste infrastructure code

## 3.2 Global Gate B — Financial safety
- [ ] Done / Not Done — Material business facts are append-only or lineage-preserving
- [ ] Done / Not Done — No silent overwrite of booked / posted / exported facts
- [ ] Done / Not Done — Corrections use explicit reverse / supersede / repost patterns where required
- [ ] Done / Not Done — Business invariants are enforced or clearly guarded
- [ ] Done / Not Done — Destructive deletes are absent or explicitly dev-only
- [ ] Done / Not Done — Monetary and quantity precision remain explicit and unchanged unintentionally

## 3.3 Global Gate C — API / behavior
- [ ] Done / Not Done — Public contract is explicit and typed
- [ ] Done / Not Done — Validation happens before side effects
- [ ] Done / Not Done — Error responses are deterministic and actionable
- [ ] Done / Not Done — Correlation id is propagated
- [ ] Done / Not Done — Idempotency is implemented where endpoint/consumer requires it
- [ ] Done / Not Done — Pagination/filter/sort behavior is explicit for list endpoints

## 3.4 Global Gate D — Async correctness
- [ ] Done / Not Done — Business write and outbox write happen in the same DB transaction where required
- [ ] Done / Not Done — Consumers are idempotent
- [ ] Done / Not Done — Aggregate ordering is explicit
- [ ] Done / Not Done — Duplicate delivery does not create duplicate business effect
- [ ] Done / Not Done — Retry behavior does not corrupt state
- [ ] Done / Not Done — Poison/failure path is visible and recoverable

## 3.5 Global Gate E — Operability
- [ ] Done / Not Done — /health exists where applicable
- [ ] Done / Not Done — /ready exists where applicable
- [ ] Done / Not Done — /info exists where applicable
- [ ] Done / Not Done — Structured logs include service name and correlation id
- [ ] Done / Not Done — Metrics or instrumentation hooks exist for changed flow
- [ ] Done / Not Done — Failure mode is diagnosable without code spelunking

## 3.6 Global Gate F — Engineering quality
- [ ] Done / Not Done — Nullability is respected
- [ ] Done / Not Done — CancellationToken is propagated where relevant
- [ ] Done / Not Done — Database/network calls are bounded by timeout/retry strategy
- [ ] Done / Not Done — No obvious N+1 / row-by-row data access in hot path
- [ ] Done / Not Done — Tests cover changed behavior at the correct layer
- [ ] Done / Not Done — Dangerous TODOs are not left in production path

---

# 4. C# service / application layer checklist

Use for application services, command handlers, use cases, orchestration code.

## 4.1 Structure
- [ ] Done / Not Done — Handler/service has a single clear responsibility
- [ ] Done / Not Done — Public method name reflects business action
- [ ] Done / Not Done — Input DTO/command is explicit
- [ ] Done / Not Done — Output/result is explicit
- [ ] Done / Not Done — Domain rules are not hidden in controller or repository glue
- [ ] Done / Not Done — CancellationToken is accepted and propagated

## 4.2 Validation and orchestration
- [ ] Done / Not Done — Input validation occurs before DB side effects
- [ ] Done / Not Done — Business validation is separated from transport validation where needed
- [ ] Done / Not Done — External calls are not performed inside DB transaction unless explicitly justified
- [ ] Done / Not Done — Transaction boundaries are explicit
- [ ] Done / Not Done — Outbox insert happens in same transaction as business write where required
- [ ] Done / Not Done — Side effects happen in deterministic order

## 4.3 Result handling
- [ ] Done / Not Done — Failures return structured result / exception consistently
- [ ] Done / Not Done — Business conflict is distinguishable from infrastructure failure
- [ ] Done / Not Done — Validation failure is distinguishable from authorization failure
- [ ] Done / Not Done — Operator-relevant identifiers are included in logs/results where appropriate

---

# 5. ASP.NET Core / REST API checklist

Use for controllers, minimal APIs, endpoint handlers, API middleware.

## 5.1 Endpoint contract
- [ ] Done / Not Done — Route naming is consistent
- [ ] Done / Not Done — HTTP method matches semantics
- [ ] Done / Not Done — Request schema is explicit
- [ ] Done / Not Done — Response schema is explicit
- [ ] Done / Not Done — Status codes are deterministic
- [ ] Done / Not Done — Breaking contract changes are identified

## 5.2 Input / output quality
- [ ] Done / Not Done — Input validation is implemented
- [ ] Done / Not Done — Validation errors are returned in structured format
- [ ] Done / Not Done — Large list endpoints support pagination
- [ ] Done / Not Done — Large list endpoints support sorting
- [ ] Done / Not Done — Large list endpoints support filtering
- [ ] Done / Not Done — Search/filter semantics are documented or obvious

## 5.3 Safety
- [ ] Done / Not Done — Material mutation endpoints require explicit confirmation model if applicable
- [ ] Done / Not Done — Idempotency strategy exists for retry-prone create/apply endpoints
- [ ] Done / Not Done — Correlation id is accepted/generated and returned/logged
- [ ] Done / Not Done — Authorization hook exists or explicit stub is in place
- [ ] Done / Not Done — No sensitive internal exception detail leaks to client
- [ ] Done / Not Done — Operator-facing errors remain actionable

## 5.4 List endpoint / tabular contract
- [ ] Done / Not Done — Server-side sorting supports requested fields intentionally
- [ ] Done / Not Done — Server-side filtering semantics map to operator use case
- [ ] Done / Not Done — Result count is provided where required
- [ ] Done / Not Done — Active sort/filter are reproducible from request
- [ ] Done / Not Done — Default sort is explicit, not accidental

## 5.5 Health and diagnostics
- [ ] Done / Not Done — /health returns liveness only
- [ ] Done / Not Done — /ready checks required dependencies
- [ ] Done / Not Done — /info returns service/version/environment
- [ ] Done / Not Done — Endpoint timing / failure is instrumented

---

# 6. PostgreSQL checklist

Use for SQL, DDL, repositories, Dapper/Npgsql queries, transaction logic.

## 6.1 Schema and integrity
- [ ] Done / Not Done — PK/FK constraints are correct
- [ ] Done / Not Done — Unique constraints match real business identity
- [ ] Done / Not Done — Nullable uniqueness is handled intentionally
- [ ] Done / Not Done — Check constraints exist where needed
- [ ] Done / Not Done — Precision/scale changes are intentional and safe
- [ ] Done / Not Done — Updated indexes match query paths

## 6.2 Source-of-truth discipline
- [ ] Done / Not Done — Business fact is stored in PostgreSQL before async publication where required
- [ ] Done / Not Done — No reliance on broker replay as primary recovery of missing DB fact
- [ ] Done / Not Done — No cache-first write path exists for canonical data
- [ ] Done / Not Done — Rebuildable projections are separated from canonical tables
- [ ] Done / Not Done — Append-only/event lineage is preserved where required

## 6.3 Query quality
- [ ] Done / Not Done — Hot path avoids SELECT *
- [ ] Done / Not Done — Query uses bounded predicates
- [ ] Done / Not Done — No accidental full-table scan on hot tables
- [ ] Done / Not Done — No row-by-row import/update loop where set-based SQL should be used
- [ ] Done / Not Done — Batch/COPY path is used or planned for heavy ingestion
- [ ] Done / Not Done — Sort/filter columns are indexed appropriately or consciously deferred

## 6.4 Transaction behavior
- [ ] Done / Not Done — Transaction scope is minimal
- [ ] Done / Not Done — Network I/O does not occur inside transaction unless explicitly justified
- [ ] Done / Not Done — Retry strategy does not duplicate business effect
- [ ] Done / Not Done — Locking behavior is understood for concurrent path
- [ ] Done / Not Done — Isolation assumption is documented in code or review notes

## 6.5 Financial data integrity
- [ ] Done / Not Done — Posting entries remain balanced where applicable
- [ ] Done / Not Done — Reverse/repost lineage exists for corrections
- [ ] Done / Not Done — Trade correction does not silently destroy historical evidence
- [ ] Done / Not Done — Settlement/posting/export states stay reconcilable

---

# 7. Redpanda / Kafka-compatible messaging checklist

Use for producers, consumers, event contracts, topic handling, outbox relay, inbox processing.

## 7.1 Producer / outbox side
- [ ] Done / Not Done — Outbox message includes required envelope fields
- [ ] Done / Not Done — event_id is explicit and stable
- [ ] Done / Not Done — aggregate_type is explicit
- [ ] Done / Not Done — aggregate_id is explicit
- [ ] Done / Not Done — aggregate_sequence is explicit
- [ ] Done / Not Done — partition_key is explicit
- [ ] Done / Not Done — correlation_id / causation_id handling is explicit
- [ ] Done / Not Done — Producer code does not invent broker ordering as business ordering

## 7.2 Consumer side
- [ ] Done / Not Done — Consumer idempotency exists
- [ ] Done / Not Done — Inbox dedupe key is correct
- [ ] Done / Not Done — Duplicate event does not duplicate business outcome
- [ ] Done / Not Done — Consumer failure leaves diagnosable state
- [ ] Done / Not Done — Poison message path exists or is explicitly stubbed
- [ ] Done / Not Done — Reprocessing does not corrupt downstream state

## 7.3 Ordering and partitioning
- [ ] Done / Not Done — Partition key is consistent with aggregate ordering needs
- [ ] Done / Not Done — aggregate_sequence is validated or respected
- [ ] Done / Not Done — Handler does not assume total ordering across partitions
- [ ] Done / Not Done — Out-of-order arrival is either tolerated or explicitly blocked
- [ ] Done / Not Done — Missing-sequence behavior is understood/documented

## 7.4 Broker discipline
- [ ] Done / Not Done — Business logic is Kafka-compatible, not vendor-specific
- [ ] Done / Not Done — No Redpanda-console-specific dependency in business path
- [ ] Done / Not Done — Topic names/versions are explicit
- [ ] Done / Not Done — Serialization format is explicit
- [ ] Done / Not Done — Headers are used intentionally, not ad hoc

## 7.5 Operability
- [ ] Done / Not Done — Consumer lag is measurable
- [ ] Done / Not Done — Publish failures are logged with enough context
- [ ] Done / Not Done — Retry count / failure count is visible
- [ ] Done / Not Done — Dead letter / parking strategy exists or is consciously deferred
- [ ] Done / Not Done — Replay strategy is understood

---

# 8. Redis checklist

Use for caching, locks, rate limiting, hot ephemeral state.

## 8.1 Correct usage
- [ ] Done / Not Done — Redis is not source of truth
- [ ] Done / Not Done — Cached data can be recomputed from canonical state
- [ ] Done / Not Done — Key naming is scoped and intentional
- [ ] Done / Not Done — TTL policy is explicit where needed
- [ ] Done / Not Done — Stale cache behavior is acceptable or handled
- [ ] Done / Not Done — Miss path is correct and safe

## 8.2 Locking / coordination
- [ ] Done / Not Done — Lock scope is explicit
- [ ] Done / Not Done — Lock timeout/expiry is explicit
- [ ] Done / Not Done — Lock failure path is explicit
- [ ] Done / Not Done — Business correctness does not depend on Redis lock alone where DB constraint is needed
- [ ] Done / Not Done — Lost lock / expired lock does not corrupt canonical state

## 8.3 Rate limiting / ephemeral state
- [ ] Done / Not Done — Rate limit keys are stable and bounded
- [ ] Done / Not Done — Counters have expiry where appropriate
- [ ] Done / Not Done — No long-lived business fact is only in Redis
- [ ] Done / Not Done — Recovery after Redis flush is acceptable

---

# 9. Outbox / Inbox special checklist

This is the strictest backend checklist in the system.

## 9.1 Outbox
- [ ] Done / Not Done — Business write and outbox insert are in same transaction
- [ ] Done / Not Done — event_id is unique and stable
- [ ] Done / Not Done — topic is explicit
- [ ] Done / Not Done — aggregate identity is explicit
- [ ] Done / Not Done — aggregate_sequence is explicit
- [ ] Done / Not Done — partition_key is explicit
- [ ] Done / Not Done — publish status transition is explicit
- [ ] Done / Not Done — publish failure increments attempts and stores last error
- [ ] Done / Not Done — relay is safe on restart

## 9.2 Inbox
- [ ] Done / Not Done — source_event_id dedupe exists
- [ ] Done / Not Done — consumer_name is part of dedupe scope
- [ ] Done / Not Done — received vs processed state is visible
- [ ] Done / Not Done — failure stores retry/error information
- [ ] Done / Not Done — duplicate messages are safe
- [ ] Done / Not Done — replay behavior is understood

---

# 10. Dapper / Npgsql repository checklist

Use for repository/query objects.

## 10.1 Query quality
- [ ] Done / Not Done — SQL is readable and intentional
- [ ] Done / Not Done — Parameters are parameterized, not interpolated unsafely
- [ ] Done / Not Done — Mapping is explicit enough to avoid silent column drift
- [ ] Done / Not Done — Multi-mapping is understandable
- [ ] Done / Not Done — Query returns only required columns
- [ ] Done / Not Done — Timeout is explicit for heavier queries where appropriate

## 10.2 Repository design
- [ ] Done / Not Done — Repository is not a god-object
- [ ] Done / Not Done — Query/repository method names reflect business or retrieval intent
- [ ] Done / Not Done — No accidental mixing of canonical write models and read projections
- [ ] Done / Not Done — Transaction/connection lifetime is clear
- [ ] Done / Not Done — Bulk operations are implemented sensibly

---

# 11. Failure handling / resilience checklist

## 11.1 Failure modes
- [ ] Done / Not Done — Validation failure path exists
- [ ] Done / Not Done — Business conflict path exists
- [ ] Done / Not Done — Dependency unavailable path exists
- [ ] Done / Not Done — Partial async failure path exists
- [ ] Done / Not Done — Duplicate message/request path exists
- [ ] Done / Not Done — Timeout path exists

## 11.2 Operator diagnosability
- [ ] Done / Not Done — Logs include identifiers needed for investigation
- [ ] Done / Not Done — Error is attributable to object / batch / event / request
- [ ] Done / Not Done — Correlation id flows through layers
- [ ] Done / Not Done — Failure is visible in monitoring or storage, not silently swallowed
- [ ] Done / Not Done — Retry vs manual intervention boundary is clear

## 11.3 Recovery
- [ ] Done / Not Done — Safe retry is possible
- [ ] Done / Not Done — Replay does not multiply side effects
- [ ] Done / Not Done — Failed partial state is inspectable
- [ ] Done / Not Done — Deadlock / transient retry does not break idempotency

---

# 12. Security / auth checklist

## 12.1 API security
- [ ] Done / Not Done — Authorization hook exists or explicit stub is present
- [ ] Done / Not Done — Sensitive identifiers are not overexposed casually
- [ ] Done / Not Done — Internal stack traces are not returned to clients
- [ ] Done / Not Done — Input validation prevents obvious abuse vectors
- [ ] Done / Not Done — Maker-checker boundary is preserved where applicable

## 12.2 Data safety
- [ ] Done / Not Done — PII is not dumped into logs casually
- [ ] Done / Not Done — Secrets are not embedded in source code
- [ ] Done / Not Done — Redis/DB/broker credentials are configuration-driven
- [ ] Done / Not Done — Audit-worthy actions are traceable

---

# 13. Testing checklist

## 13.1 Unit tests
- [ ] Done / Not Done — Domain/app logic changed is unit-tested where appropriate
- [ ] Done / Not Done — Edge conditions are covered
- [ ] Done / Not Done — Happy path only is not the whole test suite

## 13.2 Integration tests
- [ ] Done / Not Done — DB path changed is integration-tested where appropriate
- [ ] Done / Not Done — API contract changed is integration-tested where appropriate
- [ ] Done / Not Done — Outbox/inbox path changed is integration-tested where appropriate
- [ ] Done / Not Done — Serialization/deserialization path is tested where appropriate

## 13.3 Failure-path tests
- [ ] Done / Not Done — Duplicate request/event behavior is tested if relevant
- [ ] Done / Not Done — Invalid state transition is tested if relevant
- [ ] Done / Not Done — Partial failure behavior is tested or explicitly noted
- [ ] Done / Not Done — Retry/idempotency behavior is tested or explicitly noted

---

# 14. Service-specific review comments template

## 14.1 Architecture
- Done — Ownership boundary preserved
- Not Done — Service writes across boundaries
- Not Done — Canonical state leaks into cache/broker assumptions

## 14.2 API
- Done — Contract explicit and stable
- Not Done — Status code / response semantics unclear
- Not Done — Pagination/filter/sort incomplete for operator-facing list

## 14.3 Data
- Done — DB constraints support business identity
- Not Done — Business uniqueness relies only on app logic
- Not Done — Query path will not scale or is not bounded

## 14.4 Messaging
- Done — Outbox/inbox discipline respected
- Not Done — Idempotency assumed, not implemented
- Not Done — Ordering assumption unsafe

## 14.5 Safety
- Done — Material correction preserves lineage
- Not Done — Silent overwrite of material fact
- Not Done — Retry can duplicate business effect

## 14.6 Operability
- Done — Failure is diagnosable
- Not Done — Logs/metrics insufficient for investigation
- Not Done — Health/readiness/consumer lag visibility missing

---

# 15. Merge gate

A backend PR may be merged only if:

## Mandatory
- [ ] Done / Not Done — All global review gates pass
- [ ] Done / Not Done — Relevant technology-specific checklist items pass
- [ ] Done / Not Done — New/changed failure paths are covered or explicitly documented
- [ ] Done / Not Done — Canonical source-of-truth model is preserved
- [ ] Done / Not Done — Operator/investigation flow is not made worse
- [ ] Done / Not Done — Messaging and DB correctness are not hand-waved

## Optional
- [ ] Done / Not Done — Performance improved
- [ ] Done / Not Done — Instrumentation improved
- [ ] Done / Not Done — Developer ergonomics improved

If any mandatory item is “Not Done”, merge is blocked.

---

# 16. Final rule

A good backend review is not:
- “endpoint works”
- “consumer consumes”
- “query returns rows”

A good backend review is:
- does this preserve truth?
- does this preserve idempotency?
- does this preserve ordering assumptions safely?
- does this preserve operator diagnosability?
- can this fail partially without corrupting the platform?
- can the next engineer extend it without rewriting core guarantees?
