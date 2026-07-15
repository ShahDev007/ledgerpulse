"""Commercial + operations: projects, cost codes, work orders, POs, contracts, change orders."""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin


class Project(Base, PKMixin, TimestampMixin):
    __tablename__ = "projects"
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")


class CostCode(Base, PKMixin, TimestampMixin):
    __tablename__ = "cost_codes"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class WorkOrder(Base, PKMixin, TimestampMixin):
    __tablename__ = "work_orders"
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id"))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"))
    number: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="OPEN")  # OPEN | CLOSED | CANCELLED
    opened_on: Mapped[dt.date | None] = mapped_column(Date)
    closed_on: Mapped[dt.date | None] = mapped_column(Date)


class PurchaseOrder(Base, PKMixin, TimestampMixin):
    __tablename__ = "purchase_orders"
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"))
    number: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    open_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String, default="OPEN")
    effective_from: Mapped[dt.date | None] = mapped_column(Date)
    effective_to: Mapped[dt.date | None] = mapped_column(Date)


class POLine(Base, PKMixin, TimestampMixin):
    __tablename__ = "po_lines"
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"))
    description: Mapped[str] = mapped_column(String)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))


class Contract(Base, PKMixin, TimestampMixin):
    __tablename__ = "contracts"
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"))
    number: Mapped[str] = mapped_column(String, index=True)
    ceiling: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    effective_from: Mapped[dt.date | None] = mapped_column(Date)
    effective_to: Mapped[dt.date | None] = mapped_column(Date)


class ContractRate(Base, PKMixin, TimestampMixin):
    __tablename__ = "contract_rates"
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contracts.id"))
    description: Mapped[str] = mapped_column(String)
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tolerance_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0"))


class ChangeOrder(Base, PKMixin, TimestampMixin):
    __tablename__ = "change_orders"
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"))
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_orders.id"))
    number: Mapped[str] = mapped_column(String)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    approved: Mapped[bool] = mapped_column(default=False)
