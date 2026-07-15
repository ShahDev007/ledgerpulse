# LedgerPulse

**AI-native invoice tracking, cost governance, and portfolio intelligence for a vertically
integrated multifamily operator.** Interview concept for the Cadence Founding AI Engineer project.

**▶ Live demo:** https://ledgerpulse-q9aa.vercel.app — open it, pick a persona (top-right), and click around.

---

## 📖 What is this? (in plain English — no jargon)

Imagine a company that owns a bunch of **apartment buildings**. Every day, lots of people send it
**bills** ("you owe me money") — the plumber who fixed a sink, the electric company, the gardener,
the builders renovating a unit. That's a mountain of paper, and someone has to check every bill:
*Is it real? Is the amount right? Did we already pay it? Who's allowed to approve it?* Doing that by
hand is slow and easy to get wrong — you can even **pay the same bill twice** and lose money.

**LedgerPulse is a smart assistant that reads all those bills for them.** It does four things:

1. **Reads the bill automatically** — you give it a picture of a bill and AI pulls out who sent it,
   how much, and what for (real AI, reading the real document).
2. **Catches mistakes and tricks** — e.g. the same $1,240 electric bill sent twice with one letter
   changed to hide it. The assistant flags it: *"You already paid this — don't pay again."*
3. **Explains itself** — click **"Investigate with AI"** and it writes, in plain English, *why*
   something looks wrong and shows its evidence. Crucial safety rule: **the AI only advises. It can
   never approve or pay anything by itself — a human always decides.**
4. **Shows the right bills to the right people** — the money team sees every bill; a building
   manager sees only their building; a construction manager sees only their project.

**Why it matters:** it turns *"Where is that bill and did we pay it?"* into *"Every bill is sorted,
checked for mistakes, and watched by a smart helper — with no human wasting hours on it."*

### What the home screen ("Command Center") shows
It's a front-desk summary for whoever is logged in. Each box is a simple count:

| Box | What it means, plainly |
|---|---|
| **Total invoices** | How many bills are in the system. |
| **Needs review / matched** | Bills that look clean and correct. ✅ |
| **Pending approval** | Bills waiting for a person to say "yes, pay it." |
| **Open exceptions** | Bills with a **problem** that needs a human. ⚠️ |
| **Blocking (duplicates etc.)** | Problems serious enough to **freeze the bill** (e.g. a double-charge). 🛑 |
| **Duplicate-risk invoices** | Bills that look like a **repeat** of one already paid. |
| **Unbudgeted flags** | Bills for something **nobody planned to spend on** — a surprise cost. |
| **Open exposure** | Total money tied up in unpaid bills — "how much is on the table." 💵 |
| **Lifecycle** | The split of clean bills vs. bills with problems. |

*Tip: the numbers change depending on who's logged in — a building manager only sees their own
building's bills, so their totals are smaller than the company-wide finance team's.*

---

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
