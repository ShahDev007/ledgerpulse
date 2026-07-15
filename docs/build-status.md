# Build status

Phase-by-phase per the master build spec (Section 12.6). Each phase gates on an acceptance
checkpoint before the next begins.

| Phase | Scope | Status |
|---|---|---|
| 1 - Scaffold | Monorepo, Docker Compose (postgres+pgvector, redis, minio, mailpit, mock-erp), auth/personas, seed master data, health, UI shell + persona switch | ✅ done & verified |
| 2 - Invoice core | Invoice/files/audit domain, upload + AP-email intake, immutable storage + SHA-256/pHash, list/detail UI, outbox | ✅ done & verified |
| 3 - Extraction | **Live Claude** multimodal extraction, InvoiceExtraction schema, field provenance, model-run ledger, workbench + correction UI | ✅ done & verified |
| 4 - Resolution + match | Claude-based resolution; duplicate/PO/contract/WO/budget/arithmetic/risk engines with feature-level reasons; 8 seed scenarios | ✅ done & verified |
| 5 - Approval workflow | Versioned policy DSL engine, approvals + SoD + SLA, notifications, command-center KPIs (export mock in Phase 7) | ✅ done & verified |
| 6 - Exception agent | Read-only tool-scoped investigator (Opus) with allow-list + evidence citations | ✅ done & verified |
| 7 - Export + payment | Idempotent ERP export + payment sync + reconciliation; retry/permanent failure simulation | ✅ done & verified |
| 8 - Intelligence + hardening | Copilot (permission-filtered RAG), AI model dashboard, golden evals + unit tests, Playwright e2e specs, demo-reset, docs | ✅ done & verified |

## Phase 1 acceptance
- `make dev` starts all services; `api` bootstraps (schema + bucket + seed) with no manual steps.
- `GET /health`, `GET /v1/personas`, `POST /v1/personas/{id}/session`, `GET /v1/me` work.
- Web persona switcher signs in and shows role capabilities + scoped properties.
- RBAC enforced server-side (capability checks on master-data endpoints).

## Notes / decisions
- Local schema is created via `Base.metadata.create_all` in `app.bootstrap` for a zero-step
  demo; Alembic is scaffolded (`make migrate`, `make revision`) as the production path.
- **Real Claude is the default** (`LLM_PROVIDER=anthropic`). The mock provider is demoted to a
  CI/golden-eval determinism backend and an automatic fallback when no key is present - not the
  demo path.
- **Extraction** runs Claude multimodal vision on the *actual* invoice image/PDF (no separate
  OCR service required).
- **Resolution** is Claude-based (reasons over candidate master data) - **no embeddings /
  pgvector**, so no embeddings vendor or key is needed.

## Phase 1 verification (2026-07-15)
- All 8 containers up (postgres/redis/minio/mailpit/mock-erp/api/worker/web).
- API: `/health` 200; `/v1/personas` → 7 roles w/ correct capability sets; persona login issues
  JWT; `/v1/me` resolves principal; `/v1/properties` 200 with token, **401 without**.
- Web: Next.js 15 serving on :3000 (HTTP 200), persona switcher wired to the API.

## Phase 2 verification (2026-07-15)
- Upload intake → immutable original in MinIO, SHA-256 computed, `INVOICE_RECEIVED` audit event
  (hash-chained), invoice appears in inbox. File download 200.
- RBAC: Auditor (no `edit`) upload → **403**; AP Accountant → 201.
- Email intake (`/v1/intake/email`) → invoice created + **acknowledgment email in Mailpit** with
  tracking id; duplicate message-id is idempotent.
- Browser (Playwright): persona login, inbox lists both invoices, detail shows immutable
  document + SHA-256 + hash-chained audit timeline. Screenshot: `phase2-invoice-detail.png`.
- Live Claude connectivity verified (`claude-sonnet-5` round-trip) ahead of Phase 3.

## Phase 3 verification (2026-07-15)
- Synthetic invoice PDFs/PNGs rendered for all 8 scenarios (`app/demo_invoices.py`) - real
  content, no hardcoded expected values.
- **Live Claude** extraction on the actual document image via multimodal tool-use
  (schema-constrained). INV-001: vendor/number/dates/total at 0.99 confidence; digital twin
  persisted (fields, line items, 7 field-provenance rows w/ bbox+page, model-run ledger:
  claude-sonnet-5, 4621→1194 tok, 9.4s, ~$0.032).
- All 8 extracted correctly incl. **negative credit memo** (INV-007 −120.00) and the **O/0
  duplicate variant** (INV-003 `CE-1OO582` → normalized `CE100582`).
- Correction: PATCH /fields → feedback label + `FIELD_CORRECTED` audit; optimistic-lock **409**
  on stale edit.
- Browser (Playwright): workbench shows document + confidence badges + model trace + audit
  timeline; Edit/Save + Re-extract wired. Screenshot: `phase3-workbench.png`.

## Phase 4 verification (2026-07-15)
Full pipeline (resolve → duplicate → commercial match → budget → arithmetic → risk → status)
runs automatically after extraction. All 8 scenarios produced the expected flag on real
Claude-extracted data:
| Invoice | Outcome |
|---|---|
| INV-001 | MATCHED (clean) |
| INV-002 | RATE_ABOVE_CONTRACT [REVIEW] - 980 > 900 contract rate (+2%) |
| INV-003 | POSSIBLE_DUPLICATE [BLOCKING] - score 0.9184; invoice_number 1.0 via O/0 normalization |
| INV-004 | UNKNOWN_VENDOR [REVIEW] - Claude resolver returned no match for "Rainier Roofing Co" |
| INV-005 | WORK_ORDER_CLOSED [REVIEW] - WO-7710 is CLOSED |
| INV-006 | UNBUDGETED_SPEND [REVIEW] - 62000 at Maplewood, no budget |
| INV-007 | MATCHED - credit memo, correctly NOT flagged duplicate |
| INV-008 | MATCHED (clean) |
- Every match writes a `match_results` row with a feature-level reason breakdown; every
  exception carries category / severity / owner_role / evidence.
- Endpoints: `POST /v1/invoices/{id}/match`, `GET /v1/exceptions`; detail now returns
  exceptions + match_results + risk_flags + resolved vendor/property.
- Browser (Playwright): workbench issue banner + risk chips; Exception Cockpit queue with
  owner-routed summaries. Screenshot: `phase4-exception-cockpit.png`.

## Phase 5 verification (2026-07-15)
- Versioned policy DSL (`packages/policies/*.yaml`) loaded into `approval_policies`; safe
  condition evaluator; policy selection (construction vs default vs fallback) + per-step `when`.
- Submit builds steps, resolves approvers by role + property scope, enforces
  **submitter-cannot-approve**, sets SLA due dates, emails approvers (Mailpit), gates on
  **blocking exceptions**.
- Verified: INV-002 → construction_v3 → CONSTRUCTION_PM; wrong approver **403**; correct
  approver → invoice **APPROVED**; idempotent re-decide **409**; blocking-dup submit **409**.
- Command-center KPIs from `/v1/stats`; per-property cost via `/v1/analytics/property/{id}`.
- Browser (Playwright): Command Center KPI cards, Approval Queue Approve → "Invoice APPROVED",
  queue empties. Timeline chain: received → extracted → matched → submitted → decided.

## Phase 6 verification (2026-07-15)
- Read-only tool-scoped investigator agent (`services/llm/investigator.py`): Claude **Opus 4.8**
  runs an agentic loop over a fixed read tool allow-list backed by a pre-built evidence
  snapshot - structurally cannot touch the DB, mutate, mail, approve, export, or pay. Prohibited
  tools don't exist; unknown tool calls are denied.
- On INV-003 the agent called `get_invoice → search_duplicate_candidates → get_vendor_history →
  get_document_evidence → submit_findings` (4190→2144 tok, 27s) and returned BLOCKING/0.9: caught
  the O/0 OCR confusion, that the candidate is already APPROVED, the related credit memo, and
  warned about double-paying. **Every confirmed fact cites an evidence id.**
- Persists `model_runs` (capability=investigator) + `tool_calls` + findings on the exception;
  `EXCEPTION_INVESTIGATED` (MODEL) audit event. `POST /v1/invoices/{id}/investigate`.
- Browser: workbench "Investigate with AI" → cited findings panel + dual model trace
  (extract sonnet-5 + investigator opus-4-8). Screenshot: `phase6-investigator.png`.

## Phase 7 verification (2026-07-15)
- `MockErpAdapter` (HTTP → mock-erp) + export command: only APPROVED invoices export; unique
  idempotency key `(invoice, version, target)` + export ledger.
- Verified: export INV-001 → `ERP-1001` EXPORTED; **idempotent re-export** returns the same id;
  full payment 1240.50 → **RECONCILED** (terminal).
- INV-008 full lifecycle: submit → approve → export `ERP-1002` → **short payment 1600/1650 →
  PAYMENT_MISMATCH** exception, invoice PAID (not reconciled). Timeline spans all actor types:
  USER → MODEL → RULE → USER → INTEGRATION.
- Retryable vs permanent failures via mock-erp (`FAIL_RETRYABLE`→503→retryable,
  `FAIL_PERMANENT`→422→permanent). Endpoints: `POST /v1/invoices/{id}/export`,
  `/simulate-payment`. UI: Export / Record full/short payment buttons on the workbench.

## Phase 8 verification (2026-07-15)
- **Copilot** (`/v1/copilot/query`): permission-filtered RAG over the caller's in-scope invoices;
  Claude (sonnet-5) answers grounded with **invoice tracking-id citations**. Verified in browser:
  as the property-scoped Property Manager the answer was computed "over 5 invoices" (vs 8 for AP)
  - ABAC filtering - and correctly identified the duplicate, payment mismatch, and credit-memo.
  Screenshot: `phase8-copilot.png`.
- **AI model dashboard** (`/v1/model-runs`, gated on `view_model_trace`): per-capability runs,
  tokens, latency, cost, errors - governance/eval, not a black box.
- **Tests**: 6 deterministic unit tests pass (normalization, policy DSL incl. sandbox, risk).
  Live golden extraction eval (`test_golden_extraction.py`) checks header accuracy ≥94% (skipped
  without a key). Playwright e2e specs in `apps/web/e2e/`.
- **`make demo-reset`** (`app.demo_reset`): drop+recreate schema, reseed master data + policies,
  intake + live-extract + match all 8 invoices - deterministic base demo state.
- Docs: `demo-script.md` (8-min narrative), `architecture.md`, `threat-model.md`, this file.

## Summary - all 8 phases complete and verified end-to-end with live Claude.
