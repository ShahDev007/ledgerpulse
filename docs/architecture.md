# LedgerPulse Architecture

## Principle: deterministic core, probabilistic edge
Financial workflow never depends on an unconstrained agent deciding what is true. Rules,
arithmetic, identities, permissions, approval thresholds, and state transitions are
deterministic. AI is used where ambiguity is expensive: extracting messy documents, resolving
aliases, mapping free-text line items, retrieving evidence, summarizing exceptions, and
recommending coding. Every AI output carries confidence + evidence + model trace and a human
override path.

## Services (logical modules across api + worker)
- **Invoice Service** - ingestion, files, versions, extracted data, lifecycle commands, search.
- **Master Data Service** - properties, entities, vendors, GL, users, projects, cost codes, WOs.
- **Match Engine** - duplicate / PO / contract / work-order / budget matching (explainable scores).
- **Policy & Approval Service** - versioned policy DSL, approval steps, delegation, escalation, SoD.
- **AI Gateway** (`services/llm`) - provider abstraction, schema enforcement, retries, budgets,
  tool allow-lists, model-run logging.
- **Integration Service** (`services/integrations`) - import/export adapters, idempotency,
  dead-letter, reconciliation.
- **Analytics Service** - property/project/vendor/aging/forecast aggregates.
- **Notification Service** - acknowledgments, reminders, digests (via Mailpit locally).

## Containers
| Container | Port | Role |
|---|---|---|
| web | 3000 | Next.js UI |
| api | 8000 | REST + OpenAPI, command handlers, bootstrap (migrate+seed) |
| worker | - | Celery extraction/match/notify/export/payment tasks |
| postgres | 5432 | Canonical data, pgvector, outbox, audit |
| redis | 6379 | Celery broker/result + cache |
| minio | 9000/9001 | Immutable object storage |
| mailpit | 8025/1025 | Simulated AP mailbox + outbound preview |
| mock-erp | 4010 | Accounting system of record (export + payments) |

## Data integrity rules
- Money is `NUMERIC(18,2)` + Python `Decimal`, explicit currency - never floats.
- IDs are UUIDv7 (time-ordered). Timestamps are `TIMESTAMPTZ`, UTC.
- Optimistic locking (`lock_version`) on mutable rows; invoices use SQLAlchemy `version_id_col`.
- Field provenance: page + normalized bbox + method + model run + confidence.
- Constraints: unique invoice source id, export idempotency (invoice+version+target), approval
  step uniqueness.
- Audit is append-only and hash-chained (`previous_event_hash` → `event_hash`).

## Event model (transactional outbox)
Domain events are written to the `outbox` table in the same transaction as the state change; a
worker publishes them to Redis. Consumers are idempotent and keep a `processed_events` ledger,
preventing the "DB committed but event lost" failure.

## AI subsystem
| Capability | Technique | Default model | Autonomy |
|---|---|---|---|
| Classification | multimodal classifier | claude-haiku-4-5 (or mock) | auto; quarantine low-conf |
| Field/line extraction | OCR + schema-constrained multimodal | claude-sonnet-5 → opus-4-8 escalate | suggestion; review below gate |
| Vendor/property resolution | exact alias → embeddings → weighted | EmbeddingProvider (mock/voyage) | auto-link only high-conf |
| GL/capex-opex coding | policy + history retrieval + constrained LLM | claude-sonnet-5 | top-3 recommendation |
| Duplicate detection | hash + normalized keys + fuzzy + pHash | deterministic | auto-block high-risk |
| Exception investigator | tool-scoped agent, read-only | claude-opus-4-8 | recommendation w/ citations |
| Copilot | permission-filtered RAG | claude-sonnet-5 | view over controlled data |
| Approval routing | versioned policy engine | - | deterministic only |
| Payment release | external control | - | never delegated to AI |

## Auth
Persona-based dev JWT (seeded users, one per role). RBAC capability × ABAC scope enforced
server-side. Production path: Entra ID / OIDC + MFA + SCIM. Sensitive fields (tax id, bank) are
masked, separately permissioned, and excluded from the AI workflow.
