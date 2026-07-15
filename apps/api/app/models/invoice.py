"""Invoice digital twin: invoice + immutable files + versions + lines + field provenance."""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin
from app.models.enums import InvoiceStatus


class Invoice(Base, PKMixin, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "source_type", "source_external_id", name="uq_invoice_source"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    # Resolved context (nullable until resolved)
    property_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("properties.id"))
    legal_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("legal_entities.id"))
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id"))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_orders.id"))
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_orders.id"))
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"))

    # Intake / identity
    source_type: Mapped[str] = mapped_column(String)  # models.enums.SourceType
    source_external_id: Mapped[str | None] = mapped_column(String)  # e.g. email message id
    tracking_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    document_hash: Mapped[str | None] = mapped_column(String, index=True)  # SHA-256
    perceptual_hash: Mapped[str | None] = mapped_column(String, index=True)  # image pHash

    # Document fields
    raw_vendor_name: Mapped[str | None] = mapped_column(String)
    property_hint_text: Mapped[str | None] = mapped_column(String)  # extracted bill-to/property
    po_number_text: Mapped[str | None] = mapped_column(String)      # extracted PO reference
    work_order_text: Mapped[str | None] = mapped_column(String)     # extracted WO reference
    resolved_vendor_name: Mapped[str | None] = mapped_column(String)   # canonical, post-resolution
    resolved_property_name: Mapped[str | None] = mapped_column(String)
    document_type: Mapped[str] = mapped_column(String, default="invoice")
    invoice_number: Mapped[str | None] = mapped_column(String)
    invoice_number_normalized: Mapped[str | None] = mapped_column(String, index=True)
    invoice_date: Mapped[dt.date | None] = mapped_column(Date)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    service_period_start: Mapped[dt.date | None] = mapped_column(Date)
    service_period_end: Mapped[dt.date | None] = mapped_column(Date)

    # Money
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    is_credit_memo: Mapped[bool] = mapped_column(Boolean, default=False)
    supersedes_invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"))

    # Workflow / AI
    status: Mapped[str] = mapped_column(String, default=InvoiceStatus.RECEIVED.value, index=True)
    payment_status: Mapped[str] = mapped_column(String, default="NONE")
    export_status: Mapped[str] = mapped_column(String, default="NOT_EXPORTED")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    resolution_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    coding_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    risk_flags: Mapped[list | None] = mapped_column(JSONB)

    # Concurrency
    version: Mapped[int] = mapped_column(Integer, default=1)  # document/content version
    lock_version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic lock

    __mapper_args__ = {"version_id_col": lock_version}


class InvoiceFile(Base, PKMixin, TimestampMixin):
    """Immutable original (and corrected linked versions). Bytes live in object storage."""
    __tablename__ = "invoice_files"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String)
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String, index=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String)
    is_original: Mapped[bool] = mapped_column(Boolean, default=True)
    page_count: Mapped[int | None] = mapped_column(Integer)


class InvoiceLineItem(Base, PKMixin, TimestampMixin):
    __tablename__ = "invoice_line_items"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    line_no: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    suggested_gl_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gl_accounts.id"))
    capex_opex: Mapped[str | None] = mapped_column(String)
    coding_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))


class InvoiceBlob(Base, PKMixin, TimestampMixin):
    """File bytes stored in Postgres (serverless/hosted backend, no object store needed)."""
    __tablename__ = "invoice_blobs"
    storage_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String)
    data: Mapped[bytes] = mapped_column(LargeBinary)


class FieldProvenance(Base, PKMixin, TimestampMixin):
    """Field-level evidence: page + normalized bbox + method + model run + confidence."""
    __tablename__ = "field_provenance"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    field_name: Mapped[str] = mapped_column(String)
    page: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[list | None] = mapped_column(JSONB)  # [x0,y0,x1,y1] normalized
    extraction_method: Mapped[str | None] = mapped_column(String)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_runs.id"))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    raw_text: Mapped[str | None] = mapped_column(String)
