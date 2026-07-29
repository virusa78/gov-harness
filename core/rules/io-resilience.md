# I/O Resilience — Binding Agent Rule

**Effective**: 2026-06-28  
**Applies to**: All implementation touching network, messaging, streaming, or external I/O  
**Cross-refs**: target-project I/O and streaming requirements

---

## Core Principle: Durable First, Transport Second

1. Persist intent in a **durable store** (PostgreSQL outbox/inbox) inside the business transaction when financially or operationally material.
2. Call the network **outside** any open DB transaction.
3. **Classify** the failure with the project's shared taxonomy.
4. **Transient** → bounded exponential backoff + jitter via shared helpers — never hand-rolled delays.
5. **Poison / business rejection** → DLQ or terminal FAILED state — do not infinite-retry.
6. **Acknowledge** (Kafka offset commit, WS resubscribe, UI invalidate) only after durable success or an explicit skip/DLQ path.

Kafka/Redpanda is **transport only**. The project must name its durable source
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
| `TransientNetwork` | broker down, HTTP 502/503, `WebSocketException`, connection reset | Retry + backoff |
| `TransientResource` | PG deadlock, serialization failure | Retry (bounded) |
| `PermanentConfig` | 401, wrong SASL, topic misconfig | Fail fast + alert, **no** retry |
| `ContractPoison` | bad JSON, schema violation | DLQ / skip + commit offset |
| `BusinessRejected` | invariant violation | DLQ / mark FAILED |
| `UnclassifiedFatal` | NullReferenceException, unknown bugs | Fail fast + alert, **no** retry |
| `Cancelled` | shutdown token | Graceful stop |

---

## Transport-Specific Rules

### Redpanda / Kafka

- **Produce**: outbox pattern for material facts; network **never** inside DB tx.
- **Consume**: use the shared durable consumer shell; commit offset only after
  durable inbox/outbox processing or an explicit terminal path.
- **Offset**: infrastructure failure means no commit and bounded retry.
- **Poison**: persist to the project's DLQ/terminal store, then commit.

### HTTP (ClickHouse, S3, external REST)

- Wrap calls in the project's shared classified HTTP policy.
- Do not swallow `HttpRequestException` without classify + log.

### PostgreSQL

- Use the shared resilient session factory. Do not retry business logic
  blindly—only the operation explicitly declared safe.

### WebSocket / Streaming Adapters (UMDA-STR)

- Use one shared resilient client and reconnect loop.
- On upstream disconnect after a successful session, durably emit a typed
  connection-lost fact, then reconnect with the shared streaming policy.
- Unparseable vendor payloads go to a durable poison path, not silent skip.
- Give the stream a stable aggregate identity from explicit configuration.
- After reconnect: optional `AdapterConnectionRestored`; always **resubscribe** session state (SignalR groups, venue subscriptions).
- Config: `STREAMING_ADAPTER_MODE`, `STREAMING_WS_URL`, `STREAMING_ADAPTER_ID`.

### SignalR (operator push)

- Frontend reconnect covers initial connect and restores subscriptions.
- Backend push happens only after durable state change, never before commit.

### Frontend REST

- **GET/HEAD**: the shared read helper may retry transient network/gateway errors.
- **POST/PUT/PATCH**: no automatic client retry unless the contract carries
  explicit idempotency; surface a manual recovery path.

---

## Forbidden Patterns

- Copy-paste backoff/retry helpers in feature files.
- Creating a new Kafka producer **per message** in hot paths.
- Committing Kafka offset before inbox/outbox durable write.
- Holding a DB transaction open during `Produce`, HTTP, or WebSocket I/O.
- Infinite retry on poison messages or permanent config errors.
- Frontend auto-retry on mutating HTTP calls.

---

## Agent Checklist (before claiming done)

- [ ] All new I/O uses the named shared policy—no local backoff helpers.
- [ ] Material consumers use the durable consumer shell and correct offset discipline.
- [ ] Streaming/vendor adapters durably report disconnects.
- [ ] Network calls are outside DB transactions.
- [ ] Failure category and action are explicit in code or structured logs.
- [ ] Tests cover classify/retry for new adapter or consumer paths where feasible.
