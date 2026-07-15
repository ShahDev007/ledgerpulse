# LedgerPulse - 8-minute demo script

Prereqs: `cp .env.example .env`, set `ANTHROPIC_API_KEY`, `make dev`, then `make demo-reset`
(intakes + live-extracts + matches all 8 invoices). Open http://localhost:3000.

| Time | Action | Message |
|---|---|---|
| 0:00-0:45 | **Command Center** - KPIs (received, needs review, pending approval, open/blocking exceptions, exposure). | Starts in AP but becomes a shared intelligence layer for a vertically integrated operator. |
| 0:45-1:45 | **Inbox → open the clean utility invoice (INV-001, Cascade Electric)** in the Workbench. Point at the document + extracted fields + 99% confidence + model trace. | The system acknowledged the email, fingerprinted, extracted, resolved property/vendor, matched - minimal touch. Show the audit timeline. |
| 1:45-3:15 | **Open the construction invoice (INV-002, Summit)**. Show the `RATE_ABOVE_CONTRACT` exception with the feature reason (980 vs 900 +2%), linked PO/contract. | The platform compares commitment, rates, budget, and project scope - explainably. |
| 3:15-4:45 | **Open the duplicate (INV-003)**. Show the BLOCKING duplicate banner + feature breakdown, then click **Investigate with AI**. | AI is useful because it *gathers evidence and cites it*; deterministic controls + humans still decide. It caught the O/0 OCR variant and that the original is already paid. |
| 4:45-5:45 | Switch persona to **Property Manager → Approvals**, approve a routed invoice; show the invoice flip to APPROVED and the timeline. Try approving as the wrong persona (403). | Every action is explainable, permissioned, versioned, idempotent. Submitter cannot approve; blocking exceptions can’t be submitted. |
| 5:45-6:45 | On an APPROVED invoice: **Export to ERP** (idempotent) → **Record short payment** → PAYMENT_MISMATCH. | Approved records export to the system of record; payment status flows back and reconciles - or flags a mismatch. |
| 6:45-7:30 | **Copilot** - ask “Which invoices are possible duplicates or blocked, and why?” Inspect the citations. | Natural language is a view over controlled data, permission-filtered, grounded, cited - not a replacement for the ledger. |
| 7:30-8:00 | **AI dashboard** (tokens/latency/cost per capability) + close on the 30/60/90 rollout. | I can build the prototype, integrate it safely, and own the operating change. |

## The 8 seeded scenarios (what each proves)
- **INV-001** clean recurring utility → MATCHED, standard approval.
- **INV-002** construction, rate above contract → COMMERCIAL exception + PM route.
- **INV-003** O/0 duplicate → BLOCKING duplicate; investigator explains it.
- **INV-004** unknown vendor → IDENTITY exception (Claude resolver found no match).
- **INV-005** closed work order → COMMERCIAL exception.
- **INV-006** unbudgeted capital > threshold → FINANCIAL exception + asset-manager route.
- **INV-007** credit memo → classified, linked, NOT a duplicate.
- **INV-008** clean → approve → export → short payment → PAYMENT_MISMATCH.

## What to emphasize
- The model is not the system of record and the agent is not an approver.
- Deterministic core (rules, arithmetic, identity, thresholds, state) + probabilistic edge
  (extraction, resolution, coding, investigation, copilot).
- Every recommendation shows confidence + evidence + model trace + a human override path.
- Payment execution and vendor-master/bank changes are out of scope by design.
