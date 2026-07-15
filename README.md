# LedgerPulse

**AI-native invoice tracking, cost governance, and portfolio intelligence for a vertically
integrated multifamily operator.** Interview concept for the Cadence Founding AI Engineer project.

> An invoice is not a PDF to be keyed into accounting — it is an *operational event* linking a
> vendor, property, entity, work order, contract, budget, GL code, approver, payment, and
> ultimately investment performance. LedgerPulse builds that connected layer while keeping
> humans in control of every financial decision.

The AI **recommends and investigates**; it never creates vendors, changes bank details, or
releases payments. Deterministic core (rules, arithmetic, identity, thresholds, state
transitions); probabilistic edge (extraction, resolution, coding, investigation, copilot).

---

## Quick start

Requirements: Docker Desktop (Compose v2). No paid AI keys needed — the deterministic **mock**
providers run the whole demo.

```bash
cp .env.example .env
# put your ANTHROPIC_API_KEY in .env to enable live Claude (recommended)
make dev          # build + start all services; api self-migrates + seeds
make demo-reset   # intake + live-extract + match all 8 demo invoices (deterministic base state)
```

| Surface | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Mailpit (AP inbox) | http://localhost:8025 |
| MinIO console | http://localhost:9001 |
| Mock ERP | http://localhost:4010/health |

The `api` container runs `python -m app.bootstrap` on start: it waits for Postgres, creates the
schema, ensures the object-storage bucket, and seeds master data + personas — **no manual DB
steps**.

### Enable live Claude
Set in `.env`:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```
Golden evals and CI always run against the **mock** provider for determinism; live Claude is the
default interactive experience once a key is present.

> **Embeddings note:** Anthropic has no first-party embeddings API. Vendor/property resolution
> and copilot RAG use an `EmbeddingProvider` (`mock` deterministic by default, `voyage` optional).

---

## Seeded personas

Switch persona from the top-right of the web app. RBAC capabilities are enforced server-side.

| Persona | Role | Key capabilities |
|---|---|---|
| Alex Park | AP Accountant | view, edit, export |
| Priya Nair | Property Manager | view, approve |
| Chris Reyes | Construction PM | view, approve |
| Sam Ito | Asset Manager | view, approve |
| Dana Lee | Finance Admin | view, edit, approve, export, admin, audit |
| Morgan Blake | Director of Finance | view, approve, export, audit |
| Jordan Cole | Auditor | view, view_audit, view_model_trace |

---

## What's built (all 8 phases, verified end-to-end with live Claude)

- **Intake** — web upload + simulated AP email; immutable original in object storage, SHA-256 +
  perceptual hash, acknowledgment email (Mailpit).
- **Extraction** — live Claude multimodal reads the actual invoice; schema-constrained fields +
  line items, field-level provenance (page/bbox/confidence), model-run ledger, review/correct UI
  (feedback labels + optimistic locking).
- **Resolution + matching** — Claude-based vendor/property resolution; deterministic duplicate
  (feature-weighted), PO / contract-rate / work-order / budget / arithmetic checks; risk scoring —
  all with feature-level reason breakdowns.
- **Approvals** — versioned policy DSL, role + property-scoped routing, submitter-cannot-approve,
  SLA due dates, idempotent decisions.
- **Exception investigator** — read-only, tool-scoped Claude Opus agent that gathers evidence and
  returns cited findings; structurally cannot mutate anything.
- **Export + payment** — idempotent ERP export, payment sync, reconciliation, mismatch detection,
  retryable/permanent failure simulation.
- **Copilot** — permission-filtered, evidence-grounded NL queries with invoice citations.
- **Governance** — hash-chained audit on every event, AI model dashboard (tokens/latency/cost),
  transactional outbox, unit + golden-eval tests.

Screens: Command Center · Inbox · Invoice Workbench · Approval Queue · Exception Cockpit ·
Copilot · AI Model Dashboard.

## Architecture

Polyglot monorepo, Docker Compose, production-shaped:

```
apps/web        Next.js 15 + TypeScript + Tailwind + TanStack Query
apps/api        FastAPI + Pydantic v2 + SQLAlchemy 2 (async)
apps/worker     Celery tasks (extraction, matching, notify, export, payment sync)
apps/mock-erp   Simulated accounting system of record
services/       Shared: llm gateway, ocr providers, integration adapters
packages/       policies (approval DSL), ui, contracts (generated TS client)
infra/          docker-compose, postgres init, minio
fixtures/       invoices, POs, contracts, work orders, expected golden outputs
```

Details in [docs/architecture.md](docs/architecture.md). Build phases and status in
[docs/build-status.md](docs/build-status.md).

## Out of scope (stated, by design)
Payment execution and vendor-master / bank-detail changes are **not** implemented and are not
delegated to AI. The app is a sidecar control plane that exports approved records to the system
of record via provider-neutral adapters.
