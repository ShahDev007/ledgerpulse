"""Mock-ERP accounting adapter — HTTP client for the mock-erp service.

Translates the canonical invoice into the ERP payload, exports idempotently (Idempotency-Key
header), and surfaces retryable vs permanent failures so the Integration Service can choose to
retry or dead-letter.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from services.integrations.base import ExportResult, IntegrationHealth, PaymentBatch


class MockErpAdapter:
    name = "mock-erp"

    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self.base_url = base_url or os.getenv("MOCK_ERP_URL", "http://mock-erp:4010")
        self.timeout = timeout

    def health(self) -> IntegrationHealth:
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=self.timeout)
            return IntegrationHealth(healthy=r.status_code == 200, detail=r.text[:100])
        except Exception as exc:  # noqa: BLE001
            return IntegrationHealth(healthy=False, detail=str(exc))

    def export_invoice(self, invoice: dict[str, Any], idempotency_key: str) -> ExportResult:
        try:
            r = httpx.post(
                f"{self.base_url}/invoices/export",
                json=invoice,
                headers={"Idempotency-Key": idempotency_key},
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001
            return ExportResult(ok=False, retryable=True, error=f"connection: {exc}")

        if r.status_code == 200:
            data = r.json()
            return ExportResult(ok=True, external_id=data.get("external_id"))
        if r.status_code == 503:  # transient upstream
            return ExportResult(ok=False, retryable=True, error=r.text[:200])
        return ExportResult(ok=False, retryable=False, error=r.text[:200])  # 4xx permanent

    def fetch_payment_updates(self, cursor: str | None) -> PaymentBatch:
        r = httpx.get(f"{self.base_url}/payments", params={"cursor": cursor}, timeout=self.timeout)
        data = r.json()
        return PaymentBatch(cursor=data.get("cursor"), payments=[])
