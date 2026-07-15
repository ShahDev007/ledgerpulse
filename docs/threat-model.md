# Threat model (Section 8.1)

| Threat | Mitigation | Where |
|---|---|---|
| Malicious attachment | MIME verification, AV sandbox stub, file-size/page limits, no macro execution, quarantine stage | Phase 2 intake |
| Prompt injection inside invoice text | Document content is untrusted data; fixed system prompt; tool allow-list; no instruction-following from documents | `services/llm` gateway |
| Vendor impersonation / bank-change fraud | Bank + vendor-master changes are **out of scope**; out-of-band verification; sensitive fields excluded from AI workflow | by design |
| Unauthorized property/entity access | SSO (prod), RBAC capability × ABAC property/entity scope, server-side authorization, permission-filtered retrieval | `app/auth.py`, query filters |
| Data leakage to AI provider | Enterprise data terms / no-train, encryption, redaction, provider allow-list, minimum necessary context | `services/llm` |
| Model hallucination | Schema-constrained output, deterministic validation, evidence citations, confidence gate, human review | `services/llm/schemas.py`, gates |
| Approval manipulation | Immutable policy versions, segregation of duties, signed decision events, delegation controls | Phase 5 |
| Connector replay / duplication | Signed webhooks, timestamp windows, idempotency keys, export ledger | Phase 5/7 |
| Audit tampering | Append-only, hash-chained audit events; restricted service account | `app/domain/audit.py` |
| Sensitive data retention | Configurable retention, legal hold, deletion workflow, access logging | roadmap |

## Authorization model
- **RBAC** capabilities: view, edit, approve, export, admin_policy, admin_integration,
  view_audit, view_model_trace.
- **ABAC** scope: property, legal entity, project, team, classification.
- Approvers resolved at workflow creation and revalidated at decision time.
- Sensitive fields (tax id, bank) masked and separately permissioned.
- Service accounts get adapter-specific scopes only; support access off by default.

## AI governance
Model registry (approved models/versions/cost limits/rollback), prompt registry (versioned in
source control), evaluation gates (golden-set accuracy/safety/latency/cost before promotion),
permission-filtered retrieval, human override on every recommendation, drift/error monitoring,
and a deterministic/manual fallback path when AI services are unavailable.
