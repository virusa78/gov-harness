---
id: governance/rules/io-resilience
class: state
status: active
owner: governance-harness
updated: 2026-08-03
sources: [profiles/transport/nats/rules/io-resilience.md]
---

# I/O Resilience — Binding Agent Rule

**Effective**: 2026-08-03  
**Applies to**: All implementation touching network, messaging, streaming, or external I/O  
**Cross-refs**: target-project I/O and streaming requirements

---

## Core Principle: Durable First, Transport Second

1. Persist intent in a **durable store** (PostgreSQL outbox/inbox) inside the business transaction when financially or operationally material.
2. Call the network **outside** any open DB transaction.
3. **Classify** the failure with the project's shared taxonomy.
4. **Transient** → bounded exponential backoff + jitter via shared helpers — never hand-rolled delays.
5. **Poison / business rejection** → DLQ subject or terminal FAILED state — do not infinite-redeliver.
6. **Acknowledge** (NATS/JetStream ack, WS resubscribe, UI invalidate) only after durable success or an explicit skip/DLQ path.

NATS/JetStream is **transport only**. The project must name its durable source
of truth and legal archive explicitly.

---

## Shared Building Blocks

The target project must name one shared implementation for failure taxonomy,
backoff policy, durable consumer processing, database connection opening,
stream reconnect, HTTP reads and operator push. New code reuses those named
building blocks. If a building block is absent, add it once at the platform
boundary instead of creating a feature-local retry helper.

---

## Failure Categories → Actions

| Category | Examples | Action |
|----------|----------|--------|
| `TransientNetwork` | broker down, HTTP 502/503, WebSocket drop, connection reset | Retry + backoff |
| `TransientResource` | PG deadlock, serialization failure | Retry (bounded) |
| `PermanentConfig` | 401, wrong credentials/nkey, subject misconfig, missing stream | Fail fast + alert, **no** retry |
| `ContractPoison` | bad JSON, schema violation | Terminate delivery + DLQ, then ack |
| `BusinessRejected` | invariant violation | DLQ / mark FAILED |
| `UnclassifiedFatal` | segfault-class bugs, unknown exceptions | Fail fast + alert, **no** retry |
| `Cancelled` | shutdown signal | Graceful stop |

---

## Transport-Specific Rules

### NATS / JetStream

- **Publish**: outbox pattern for material facts; network **never** inside DB tx.
  Material publishes go through JetStream with publish-ack checked; plain NATS
  publish is fire-and-forget and allowed only for immaterial signals.
- **Consume**: use the shared durable consumer shell with explicit ack
  (`AckExplicit`); ack only after durable inbox/outbox processing or an
  explicit terminal path.
- **Redelivery**: infrastructure failure means no ack (or nak with delay) and
  bounded redelivery; `max_deliver` is always explicit — never unlimited.
- **Poison**: persist to the project's DLQ subject or terminal store, then
  terminate the delivery (`term`) so it is not redelivered.
- **Identity**: durable consumer names come from explicit configuration, not
  generated per process start — otherwise redelivery state is silently lost.
- **Request/reply**: every request carries an explicit timeout; a missing
  responder is classified (`TransientNetwork` vs `PermanentConfig`), not
  swallowed.

### HTTP (object storage, external REST)

- Wrap calls in the project's shared classified HTTP policy.
- Do not swallow HTTP client exceptions without classify + log.

### PostgreSQL

- Use the shared resilient session factory. Do not retry business logic
  blindly—only the operation explicitly declared safe.

### WebSocket / Streaming

- Use one shared resilient client and reconnect loop.
- On upstream disconnect after a successful session, durably emit a typed
  connection-lost fact, then reconnect with the shared streaming policy.
- Unparseable payloads go to a durable poison path, not silent skip.
- Give the stream a stable identity from explicit configuration.
- After reconnect: always **resubscribe** session state (subjects, queue
  groups, session channels).

### Operator push (WS/SSE)

- Frontend reconnect covers initial connect and restores subscriptions.
- Backend push happens only after durable state change, never before commit.

### Frontend REST

- **GET/HEAD**: the shared read helper may retry transient network/gateway errors.
- **POST/PUT/PATCH**: no automatic client retry unless the contract carries
  explicit idempotency; surface a manual recovery path.

---

## Forbidden Patterns

- Copy-paste backoff/retry helpers in feature files.
- Creating a new NATS connection **per message** in hot paths.
- Acking a JetStream delivery before the inbox/outbox durable write.
- Unbounded `max_deliver` on any durable consumer.
- Holding a DB transaction open during publish, HTTP, or WebSocket I/O.
- Infinite redelivery of poison messages or permanent config errors.
- Frontend auto-retry on mutating HTTP calls.

---

## Agent Checklist (before claiming done)

- [ ] All new I/O uses the named shared policy—no local backoff helpers.
- [ ] Material consumers use the durable consumer shell and correct ack discipline.
- [ ] Streaming adapters durably report disconnects.
- [ ] Network calls are outside DB transactions.
- [ ] Failure category and action are explicit in code or structured logs.
