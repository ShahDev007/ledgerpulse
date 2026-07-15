"""Organization / ownership hierarchy: org → legal entities → properties → buildings → units."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin


class Organization(Base, PKMixin, TimestampMixin):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class LegalEntity(Base, PKMixin, TimestampMixin):
    __tablename__ = "legal_entities"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str | None] = mapped_column(String)


class Property(Base, PKMixin, TimestampMixin):
    __tablename__ = "properties"
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    legal_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("legal_entities.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String)
    active_from: Mapped[dt.date | None] = mapped_column(Date)
    active_to: Mapped[dt.date | None] = mapped_column(Date)


class Building(Base, PKMixin, TimestampMixin):
    __tablename__ = "buildings"
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)


class Unit(Base, PKMixin, TimestampMixin):
    __tablename__ = "units"
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    building_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("buildings.id"))
    label: Mapped[str] = mapped_column(String, nullable=False)
