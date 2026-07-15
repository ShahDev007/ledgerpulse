"""Schema-constrained I/O for the AI subsystem (Appendix A.2, A.4, A.5).

Every model call returns one of these validated shapes. Validation happens at the
gateway boundary; the gateway retries the provider on a schema mismatch.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

BBox = tuple[float, float, float, float]


class ExtractedField(BaseModel):
    """A single extracted value with its evidence and confidence."""
    value: str | Decimal | date | None = None
    confidence: float = Field(ge=0, le=1, default=0.0)
    page: int | None = None
    bbox: BBox | None = None
    raw_text: str | None = None


class ExtractedInvoiceLine(BaseModel):
    description: ExtractedField
    quantity: ExtractedField
    unit_price: ExtractedField
    amount: ExtractedField


class InvoiceExtraction(BaseModel):
    document_type: Literal["invoice", "credit_memo", "statement", "receipt", "other"]
    vendor_name: ExtractedField
    invoice_number: ExtractedField
    invoice_date: ExtractedField
    due_date: ExtractedField
    property_hint: ExtractedField
    purchase_order_number: ExtractedField
    work_order_number: ExtractedField | None = None
    subtotal: ExtractedField
    tax: ExtractedField
    total: ExtractedField
    currency: ExtractedField
    lines: list[ExtractedInvoiceLine] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CodingCandidate(BaseModel):
    gl_account_id: str
    cost_code_id: str | None = None
    capex_opex: Literal["CAPEX", "OPEX"]
    probability: float = Field(ge=0, le=1)
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class CodingRecommendation(BaseModel):
    candidates: list[CodingCandidate] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    policy_conflicts: list[str] = Field(default_factory=list)


class InvestigatorResult(BaseModel):
    """Read-only exception investigator output (Appendix A.5)."""
    issue_type: str
    severity: Literal["INFO", "REVIEW", "BLOCKING"]
    summary: str
    confirmed_facts: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommended_action: str
    requested_information: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    draft_message: str | None = None


class DocumentClassification(BaseModel):
    document_type: Literal["invoice", "credit_memo", "statement", "receipt", "other"]
    confidence: float = Field(ge=0, le=1)
