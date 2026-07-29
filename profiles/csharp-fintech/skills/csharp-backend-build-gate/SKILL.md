---
name: csharp-backend-build-gate
description: Pre/during-code quality gate for C# backend agents (ASP.NET Core REST, Dapper/Npgsql, PostgreSQL, Redis, Redpanda/Kafka). 22-section rule system with EARS tags. Apply BEFORE and WHILE writing C# backend code. Companion to backend-code-review-csharp (post-code).
license: MIT
metadata:
  category: build-gate
  complexity: advanced
  author: gov-harness
  version: 1.2
---

## Spec-Driven Protocol (mandatory)

This skill operates within the SDD framework. When writing C# backend code:
- Map every implementation decision to a requirement ID from the Requirement Matrix
- Classify each gate rule by **EARS type**: Ubiquitous, Event-Driven, Unwanted Behaviour, State-Driven, Optional Feature, Complex
- Cite gate IDs (`GATE-N`) as evidence in the Capability Matrix (phase 5)
- Flag missing EARS classification as an SDD protocol gap

**Authority:** this installed profile is the portable build-gate source.
Project-local rules may add stricter constraints but may not silently weaken
it. Any local override is declared in `.harness.lock`.

**Companion skill:** `backend-code-review-csharp` is the **post-code acceptance review**. This skill is the **pre/during-code build gate**. Load both when working on C# backend code.

---

# When to load this skill

Load `csharp-backend-build-gate` when ANY of these is true:
- You are about to write or modify C# backend code (ASP.NET Core, Dapper, Npgsql, PostgreSQL, Redis, Redpanda/Kafka)
- The target file lives under `src/Services/<ServiceName>/` or `src/BuildingBlocks/`
- The ticket mentions `.cs`, `Program.cs`, `Features/`, `Endpoints/`, `Handlers/`, `Persistence/`
- The SDD orchestrator dispatched a C# backend ticket (the prompt will reference the gate path)

Do NOT load for:
- Frontend work (use the target project's frontend review capability)
- Pure SQL migrations without C# surface
- Python tooling in `scripts/code-graph/`
- Node.js orchestrator code in `scripts/`

---

# Pre-code protocol (Phase 2 Design entry gate — `GATE-18`)

Before writing ANY code, answer these 12 questions. If you cannot answer them, do NOT write code yet — request clarification or read more context.

```text
1. What endpoint/feature am I implementing?
2. Is it tenant-scoped, system-scoped, or admin-scoped?
3. What is the typed request?
4. What is the typed response?
5. What validation is required?
6. What DB tables are read/written?
7. What transaction boundary is required?
8. What idempotency mechanism is used?
9. Is outbox required?
10. Is audit required?
11. What state transitions are allowed?
12. What tests prove this?
```

---

# Post-code protocol (Phase 5 Verification exit gate — `GATE-19`)

Before claiming completion, verify all 12 items. Each item references a gate rule that MUST pass.

```text
1. Program.cs contains no business SQL or heavy endpoint logic.    [GATE-3]
2. All endpoint request bodies are typed.                          [GATE-1.2]
3. No dynamic is used for API payloads.                            [GATE-1.2]
4. All SQL is parameterized and placed in repository/query layer.  [GATE-8]
5. CancellationToken is propagated.                                [GATE-4.2]
6. Tenant/system/admin scope is explicit.                          [GATE-6]
7. No raw exception messages are returned.                         [GATE-1.4]
8. Audit actor is not confused with tenant id.                     [GATE-1.6]
9. Mutations have idempotency strategy.                            [GATE-10]
10. Outbox exists where downstream observation is required.        [GATE-11]
11. Tests were added or updated.                                   [GATE-17]
12. Legacy stubs are removed.                                      [GATE-1.7]
13. `dotnet build` passes for every touched `.csproj`.             [GATE-19.1]
```

**Compile step (mandatory before claiming done):**

```bash
# Run for each csproj you touched; fix all errors before Phase 5 sign-off.
dotnet build src/Services/<ServiceName>/<ServiceName>.csproj --no-restore
```

If build fails, do NOT claim completion — fix compile errors in the same L0 pass.

---

# Platform copy-first gate (`GATE-39`) [EARS: Event-Driven — WHEN implementing Kafka consumers, inbox, or projection writes]

**Note:** GATE-31 in the canonical doc is Maintainability; platform copy-first is **GATE-39**.

Before writing ANY consumer/inbox/projection code, the agent MUST read and cite these canonical sources (copy pattern, do not reinvent):

| Topic | Canonical file(s) |
|---|---|
| Idempotent consumer + offset commit | `src/BuildingBlocks/Superfront.Messaging/C0Consumer.cs` |
| Inbox dedup / claim / mark processed | `src/BuildingBlocks/Superfront.Messaging/InboxGuard.cs` (or same folder) |
| Inbox DDL | `db/02_full_ddl.sql` → `infra.inbox_messages` |
| Projection positions DDL | `db/02_full_ddl.sql` or `src/Migrations/V023_create_projection_schema.sql` → `projection.positions` |
| Position upsert (delta/VWAP) | `src/Workers/ProjectionWorker/Features/Projection/Persistence/PositionRepository.cs` |

## `GATE-39.1` Required pre-code steps [Ubiquitous for messaging tickets]

```text
1. grep/read DDL for every table you INSERT/UPDATE
2. grep for existing C0Consumer usage in repo (copy call pattern)
3. Name copied files in Design Checklist before Phase 4
4. Do NOT invent inbox column names (consumer_name, source_event_id, etc.)
```

## `GATE-39.2` Forbidden [Unwanted Behaviour]

```text
custom manual consume loop when C0Consumer applies
custom infra.inbox_messages INSERT with columns not in DDL
writing to portfolio.positions when ticket targets projection.positions
duplicate local EventEnvelope type when Superfront.Common.EventEnvelope exists
committing Kafka offset when DB transaction rolled back
```

## `GATE-39.3` Handler contract [Event-Driven]

Handler for Kafka path MUST accept `(NpgsqlConnection, IDbTransaction, EventEnvelope, …)` inside C0Consumer callback, OR delegate to repository called only after InboxGuard claim within the same transaction C0Consumer holds.

---

# Absolute hard rules (`GATE-1`)

All rules in §1 are **EARS: Ubiquitous** — always true regardless of state.

## `GATE-1.1` No giant Program.cs
Business logic MUST live in `Features/<FeatureName>/{Contracts,Endpoints,Handlers,Validators,Queries,Commands,Persistence}/`. `Program.cs` may contain only: host builder, configuration, logging, DI, middleware, endpoint group mapping, `app.Run()`.

## `GATE-1.2` No dynamic request bodies
Forbidden: `app.MapPost("/...", async (dynamic req) => { ... });`
Required: strongly typed `record` request/response contracts.

## `GATE-1.3` No unstructured business endpoints [Optional Feature]
Each endpoint MUST have: typed request, typed response, validation, known status codes, OpenAPI metadata, correlation id, tenant behavior, authorization placeholder, tests.

## `GATE-1.4` No raw exception leaks [Unwanted Behaviour]
Forbidden: `return Results.Problem(ex.Message);`
Required: log internally, return stable ProblemDetails with correlation_id, do not leak stack/SQL/credentials.

## `GATE-1.5` No hidden cross-tenant access [Ubiquitous for tenant-scoped data]
Every tenant-scoped SQL query MUST include `tenant_id`. Mark each endpoint: tenant-scoped, system-scoped, admin-scoped, public-health.

## `GATE-1.6` No fake audit
Distinguish: `tenant_id`, `actor_user_id`, `service_name`, `performed_by`, `correlation_id`. Never write tenant id into `performed_by` unless that column is explicitly actor identity.

## `GATE-1.7` No legacy stubs in production service
Forbidden: bare `app.MapGet/MapPost/MapDelete` CRUD stubs in finished services.

---

# Required backend structure (`GATE-2`)

```text
src/Services/<ServiceName>/
  Program.cs
  Composition/
    ServiceCollectionExtensions.cs
    EndpointRouteBuilderExtensions.cs
  Middleware/
    CorrelationIdMiddleware.cs
    TenantContextMiddleware.cs
    ErrorHandlingMiddleware.cs
  Common/
    RequestContext.cs
    AppError.cs
    ApiResult.cs
    ProblemDetailsFactory.cs
  Features/<FeatureName>/
    Contracts/
    Endpoints/
    Handlers/
    Validators/
    Persistence/
  Tests/
```

---

# Program.cs gate (`GATE-3`)

Allowed inside `Program.cs`: `WebApplication.CreateBuilder`, `AddServiceDefaults`, DI registration, `builder.Build`, `UseServiceDefaults`, `MapRegistryEndpoints` (or equivalent), `app.Run`.

Forbidden inside `Program.cs`: SQL strings, Dapper calls, transaction logic, business validation, audit insert logic, JSON parsing of business fields, endpoint bodies longer than route delegation.

---

# Endpoint gate (`GATE-4`) [Optional Feature — per endpoint]

## 4.1 Contract
Request typed | Response typed | Error model typed | Route name stable | HTTP method semantic | Versioning explicit | OpenAPI metadata.

## 4.2 Execution
Delegates to handler | No SQL in endpoint | No transaction logic in endpoint | Accepts CancellationToken | Uses RequestContext | Returns stable status codes.

## 4.3 Error handling
400 with stable code on validation | 404 with stable code on not-found | 409 with stable code on conflict | Middleware handles unexpected | No internal exception leak.

---

# RequestContext gate (`GATE-5`)

Every business request MUST carry:
```csharp
public sealed record RequestContext(
    Guid? TenantId,
    Guid CorrelationId,
    string? ActorUserId,
    string ServiceName,
    DateTimeOffset NowUtc
);
```

`CorrelationId` always required. `ActorUserId` MUST NOT be faked from tenant id. `NowUtc` SHOULD be injected via time provider.

---

# Tenant scope gate (`GATE-6`) [State-Driven]

- `TENANT_SCOPED` — `X-Tenant-Id` required, `tenant_id` in queries/audit/outbox.
- `SYSTEM_SCOPED` — no tenant header by default. If writes audit, use actor/service identity.
- `ADMIN_SCOPED` — explicit admin authorization policy required.
- `PUBLIC_HEALTH` — `/health`, `/ready`, `/info`.

---

# Validation gate (`GATE-7`)

Validation MUST run before side effects. Allowed: FluentValidation, manual validator class, strong domain validation object. Not allowed: scattered `if` in endpoint body, UI-only validation, DB exception as primary validation.

Validation MUST cover: required strings, identifier format, enum values, positive versions, date/time windows, JSON shape, tenant scope, state transition legality.

On failure, return stable machine-readable error:
```json
{ "code": "VALIDATION_FAILED", "message": "...", "correlation_id": "..." }
```

---

# PostgreSQL / Dapper gate (`GATE-8`)

## 8.1 SQL placement
SQL lives in `Persistence/<Feature>Repository.cs` or `Persistence/<Feature>Sql.cs`. Forbidden in `Program.cs`, endpoint lambdas, controller actions.

## 8.2 Query rules
Parameterized | No string interpolation for values | Tenant-scoped queries include `tenant_id` | Explicit SELECT columns | Hot-path bounded | List queries paginated | Server-side filter/sort for grids | Explicit command timeout for heavy commands.

## 8.3 Mapping rules
Forbidden unless justified: `QueryAsync<dynamic>`, `QueryFirstOrDefaultAsync<dynamic>`. Use typed `T`. Private persistence DTOs allowed if DB shape differs from API response.

## 8.4 Transaction rules
Explicit boundary | As short as possible | No network I/O inside | Commit after all DB side effects | Safe rollback | CancellationToken propagated.

---

# State transition gate (`GATE-9`) [State-Driven for lifecycle objects]

Required: explicit transition matrix, handler checks current state, invalid transition → 409 Conflict, transition audited, timestamps preserved. Implement transitions in one place, not scattered.

Example (schema versions): `ACTIVE → DEPRECATED`, `DEPRECATED → RETIRED`. `ACTIVE → RETIRED` forbidden unless explicitly allowed. `RETIRED → ACTIVE` forbidden.

---

# Idempotency gate (`GATE-10`) [State-Driven — WHEN retry-prone]

Every retry-prone mutation MUST have an idempotency strategy. Retry-prone examples: register schema version, register event type, apply repair, apply amendment, import file, create execution from external message.

The agent MUST name the mechanism: natural unique key, idempotency key, external id, event id, canonical hash, database constraint, inbox dedupe. If no mechanism — endpoint is Not Done.

---

# Outbox / eventing gate (`GATE-11`) [Event-Driven]

If a mutation changes something other services/workers must observe, write an outbox event in the same DB transaction.

Required event envelope fields: `event_id`, `tenant_id` (if tenant-scoped), `event_type`, `event_version`, `aggregate_type`, `aggregate_id`, `aggregate_sequence`, `partition_key`, `correlation_id`, `causation_id`, `occurred_at`, `producer`, `payload`.

Outbox rules: same transaction as business write | deterministic `aggregate_sequence` | `partition_key` matches aggregate | duplicate command cannot create duplicate event | publish failure diagnosable. If service intentionally does not emit events, state why.

---

# Redpanda / Kafka-compatible gate (`GATE-12`)

No Redpanda-specific business logic. Use Kafka-compatible APIs. No business dependency on Redpanda Console. No vendor-specific assumptions. No assumption of total ordering across topics/partitions.

Every consumer MUST have: inbox dedupe, idempotent handler, bounded retry, poison message strategy, structured logs, correlation id propagation, consumer lag metric.

---

# Redis gate (`GATE-13`) [Optional Feature]

Redis MAY be used only for: cache, short locks, rate limits, hot ephemeral state. Forbidden: canonical business state, schema registry truth, posting state, settlement state.

Every Redis usage MUST define: key pattern, TTL policy, miss behavior, stale behavior, flush recovery behavior. If correctness depends on Redis lock, there MUST also be a DB constraint/DB-side guard.

---

# Audit gate (`GATE-14`) [Event-Driven — WHEN material mutation]

Every material mutation MUST write audit. Audit MUST include: `tenant_id` (if tenant-scoped), `actor_user_id` or service identity, action, `resource_type`, `resource_id`, before/after or details hash, `correlation_id`, outcome, timestamp.

Audit MUST NOT store raw PII casually, secrets, misleading actor identity, or hide failed attempts. Audit write in same transaction as the material state change where appropriate.

---

# Logging / observability gate (`GATE-15`)

Every service MUST support: structured JSON logs, correlation id, service name, service version, environment, health/ready/info endpoints, basic metrics hooks.

Mutation flow logs MUST include: `correlation_id`, `tenant_id` (if relevant), actor/service identity, resource id, action, outcome, duration.

Logs MUST NOT include: secrets, passwords, raw tokens, unbounded payloads, PII unless explicitly allowed.

---

# REST list endpoint / grid gate (`GATE-16`) [Optional Feature — WHEN feeding operator table]

Required: pagination, server-side sorting, server-side filtering, quick search, `total_count`, stable default sort, reproducible query. Returning unbounded lists is forbidden for operator-facing tables.

Recommended request model:
```csharp
public sealed record GridQueryRequest(
    int Page,
    int PageSize,
    IReadOnlyList<GridSort> Sort,
    GridFilterGroup? Filters,
    string? Search,
    string SearchMode
);
```

---

# Tests gate (`GATE-17`)

For each feature: validator tests, handler tests, repository integration tests (if SQL changed), endpoint tests (if API changed), state transition tests (if lifecycle changed), idempotency tests (for retry-prone mutations), failure-path tests (for important failure modes).

---

# Final instruction (`GATE-22`)

Do NOT optimize for fewer files. Optimize for: clear boundaries, typed contracts, safe mutations, idempotency, diagnosability, testability, operator support, future maintainability. If this produces more files than a single `Program.cs`, that is correct.

---

# SDD Phase Mapping (Appendix A)

| Gate ID | SDD Phase | Used As |
|---------|-----------|---------|
| GATE-1.1 – 1.7 | Phase 2 (Design) | Design Checklist input |
| GATE-2 | Phase 2 (Design) | component_responsibilities |
| GATE-3 | Phase 4 (Implementation) | Pre-write constraint |
| GATE-4 | Phase 4 + Phase 5 | Endpoint Done/Not Done |
| GATE-5 | Phase 2 (Design) | interfaces_defined |
| GATE-6 | Phase 2 (Design) | security |
| GATE-7 | Phase 4 (Implementation) | Validation rule |
| GATE-8 | Phase 4 + Phase 5 | SQL placement + mapping check |
| GATE-9 | Phase 2 + Phase 5 | State machine check |
| GATE-10 | Phase 2 (Design) | Idempotency strategy named |
| GATE-11 | Phase 2 + Phase 4 | Outbox design + write |
| GATE-12 | Phase 4 | Consumer contract |
| GATE-13 | Phase 2 | Cache scope decision |
| GATE-14 | Phase 4 + Phase 5 | Audit write verification |
| GATE-15 | Phase 4 | Observability hooks |
| GATE-16 | Phase 2 + Phase 4 | Grid endpoint design |
| GATE-17 | Phase 5 (Verification) | Test evidence |
| GATE-18 | Phase 2 entry gate | Pre-code answers required |
| GATE-19 | Phase 5 exit gate | Post-code verification |
| GATE-39 | Phase 2 + Phase 4 | Platform copy-first (Kafka/inbox/projection) |
| GATE-22 | Phase 4 | File structure principle |

---

# EARS Type Summary (Appendix B)

EARS = Easy Approach to Requirements Syntax. Six types:
- **Ubiquitous** — "The system shall ..." (always true)
- **Event-Driven** — "When [trigger], the system shall ..."
- **Unwanted Behaviour** — "If [condition], then the system shall ..."
- **State-Driven** — "While [state], the system shall ..."
- **Optional Feature** — "Where [feature included], the system shall ..."
- **Complex** — combination of the above
