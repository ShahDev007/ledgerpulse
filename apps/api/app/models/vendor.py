"""Vendor identity + aliases (for resolution) and risk events."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin


class Vendor(Base, PKMixin, TimestampMixin):
    __tablename__ = "vendors"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    remit_to_address: Mapped[str | None] = mapped_column(String)
    # Sensitive: masked + separately permissioned + excluded from AI workflow (Section 8.2)
    tax_id_hash: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")  # ACTIVE | INACTIVE | PENDING
    has_w9: Mapped[bool] = mapped_column(Boolean, default=False)
    has_insurance: Mapped[bool] = mapped_column(Boolean, default=False)


class VendorAlias(Base, PKMixin, TimestampMixin):
    __tablename__ = "vendor_aliases"
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"))
    alias: Mapped[str] = mapped_column(String, nullable=False, index=True)


class VendorRiskEvent(Base, PKMixin, TimestampMixin):
    __tablename__ = "vendor_risk_events"
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"))
    kind: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(String)
