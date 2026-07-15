"""Mock accounting system of record.

Simulates the external ERP the Integration Service exports to and reads payments from.
Behaviour is deterministic and controllable so the demo can show idempotent retries and
retryable-vs-permanent failures (Section 12.1 #9).

Endpoints:
  GET  /health
  GET  /master-data           -> seed master data batch (cursor-paginated stub)
  POST /invoices/export       -> idempotent export; honours Idempotency-Key header
  GET  /payments              -> payment status updates (cursor stub)

Failure simulation: include "FAIL_RETRYABLE" or "FAIL_PERMANENT" in the invoice number
to exercise the connector's retry/dead-letter paths.
"""
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock ERP", version="0.1.0")

# In-memory idempotency ledger: idempotency_key -> external_id
_EXPORTS: dict[str, str] = {}
_SEQ = {"n": 1000}


class ExportPayload(BaseModel):
    invoice_id: str
    invoice_number: str | None = None
    invoice_version: int = 1
    total: float | None = None
    vendor: str | None = None
    property: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-erp"}


@app.get("/master-data")
def master_data(cursor: str | None = None):
    # The demo seeds master data directly in Postgres; this endpoint exists to prove the
    # sync_master_data adapter contract and returns an empty, terminal batch.
    return {"cursor": None, "records": [], "has_more": False}


@app.post("/invoices/export")
def export_invoice(payload: ExportPayload, idempotency_key: str = Header(...)):
    number = (payload.invoice_number or "").upper()
    if "FAIL_PERMANENT" in number:
        raise HTTPException(status_code=422, detail="Permanent validation error (mock)")
    if "FAIL_RETRYABLE" in number:
        raise HTTPException(status_code=503, detail="Temporary upstream error (mock)")

    if idempotency_key in _EXPORTS:  # idempotent replay
        return {"external_id": _EXPORTS[idempotency_key], "idempotent_replay": True}

    _SEQ["n"] += 1
    external_id = f"ERP-{_SEQ['n']}"
    _EXPORTS[idempotency_key] = external_id
    return {"external_id": external_id, "idempotent_replay": False}


@app.get("/payments")
def payments(cursor: str | None = None):
    return {"cursor": None, "payments": []}
