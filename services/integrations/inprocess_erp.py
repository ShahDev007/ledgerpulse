"""In-process ERP adapter — same behavior as the mock-erp service, no HTTP/extra container.

Used on serverless/hosted deployments (ERP_MODE=inprocess). Idempotency is enforced upstream by
the export ledger (Export table), so this just mints an external id and honors failure tokens.
"""
from __future__ import annotations

import hashlib
from typing import Any

from services.integrations.base import ExportResult, IntegrationHealth, PaymentBatch


class InProcessErpAdapter:
    name = "mock-erp"

    def health(self) -> IntegrationHealth:
        return IntegrationHealth(healthy=True, detail="in-process")

    def export_invoice(self, invoice: dict[str, Any], idempotency_key: str) -> ExportResult:
        number = (invoice.get("invoice_number") or "").upper()
        if "FAIL_PERMANENT" in number:
            return ExportResult(ok=False, retryable=False, error="Permanent validation error (mock)")
        if "FAIL_RETRYABLE" in number:
            return ExportResult(ok=False, retryable=True, error="Temporary upstream error (mock)")
        ext = "ERP-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:6].upper()
        return ExportResult(ok=True, external_id=ext)

    def fetch_payment_updates(self, cursor: str | None) -> PaymentBatch:
        return PaymentBatch(cursor=None, payments=[])
