"""Provider-neutral accounting connector interface (Section 5.4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


@dataclass
class IntegrationHealth:
    healthy: bool
    detail: str = ""


@dataclass
class SyncBatch:
    cursor: str | None
    records: list[dict[str, Any]] = field(default_factory=list)
    has_more: bool = False


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class ExportResult:
    ok: bool
    external_id: str | None = None
    retryable: bool = False
    error: str | None = None


@dataclass
class PaymentUpdate:
    invoice_external_id: str
    status: str
    amount: Decimal
    reference: str
    paid_at: str | None = None


@dataclass
class PaymentBatch:
    cursor: str | None
    payments: list[PaymentUpdate] = field(default_factory=list)


@runtime_checkable
class AccountingAdapter(Protocol):
    """Adapters transform between the canonical model and an external system."""

    def health(self) -> IntegrationHealth: ...
    def sync_master_data(self, cursor: str | None) -> SyncBatch: ...
    def validate_invoice(self, invoice: dict[str, Any]) -> ValidationResult: ...
    def export_invoice(self, invoice: dict[str, Any], idempotency_key: str) -> ExportResult: ...
    def fetch_payment_updates(self, cursor: str | None) -> PaymentBatch: ...
