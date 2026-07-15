"""Accounting/ERP integration adapters (Section 5.4).

The canonical model is provider-neutral; adapters translate to/from Yardi, AppFolio,
RealPage, Entrata, NetSuite, QuickBooks, Sage, Procore, or (here) the mock-erp service.
"""
from services.integrations.base import (
    AccountingAdapter,
    ExportResult,
    IntegrationHealth,
    PaymentBatch,
    SyncBatch,
    ValidationResult,
)

__all__ = [
    "AccountingAdapter",
    "ExportResult",
    "IntegrationHealth",
    "PaymentBatch",
    "SyncBatch",
    "ValidationResult",
]
