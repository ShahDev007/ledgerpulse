"""Finance: GL accounts, budgets, payments, export ledger."""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin


class GLAccount(Base, PKMixin, TimestampMixin):
    __tablename__ = "gl_accounts"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    default_capex_opex: Mapped[str | None] = mapped_column(String)  # CAPEX | OPEX
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Budget(Base, PKMixin, TimestampMixin):
    __tablename__ = "budgets"
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)


class BudgetLine(Base, PKMixin, TimestampMixin):
    __tablename__ = "budget_lines"
    budget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("budgets.id"))
    cost_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cost_codes.id"))
    gl_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gl_accounts.id"))
    original_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    revised_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    committed: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    actual: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))


class Payment(Base, PKMixin, TimestampMixin):
    __tablename__ = "payments"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String)  # models.enums.PaymentStatus
    reference: Mapped[str | None] = mapped_column(String)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    reconciled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Export(Base, PKMixin, TimestampMixin):
    """Export ledger — enforces one export per invoice version + target (idempotency)."""
    __tablename__ = "exports"
    __table_args__ = (
        UniqueConstraint("invoice_id", "invoice_version", "target_system", name="uq_export_idem"),
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    invoice_version: Mapped[int] = mapped_column()
    target_system: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    external_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # models.enums.ExportStatus
    error: Mapped[str | None] = mapped_column(String)
