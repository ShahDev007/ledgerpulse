"""Identity: users (with a role), teams, and delegations.

Property/project scope is stored as arrays of ids to power ABAC narrowing.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin


class User(Base, PKMixin, TimestampMixin):
    __tablename__ = "users"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # models.enums.Role value
    team: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # ABAC scope
    property_scope: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    project_scope: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    approval_limit: Mapped[float | None] = mapped_column(Numeric(18, 2))


class Delegation(Base, PKMixin, TimestampMixin):
    __tablename__ = "delegations"
    from_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    starts_on: Mapped[dt.date] = mapped_column(Date)
    ends_on: Mapped[dt.date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
