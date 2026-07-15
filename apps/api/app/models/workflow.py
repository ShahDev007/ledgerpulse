"""Workflow: approval policies, approval requests/steps, exceptions, notifications, tasks."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin


class ApprovalPolicy(Base, PKMixin, TimestampMixin):
    """Versioned policy loaded from packages/policies/*.yaml (immutable once active)."""
    __tablename__ = "approval_policies"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_policy_version"),)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSONB)  # parsed DSL
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalRequest(Base, PKMixin, TimestampMixin):
    __tablename__ = "approval_requests"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    policy_name: Mapped[str] = mapped_column(String)
    policy_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="PENDING")  # PENDING|APPROVED|REJECTED
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ApprovalStep(Base, PKMixin, TimestampMixin):
    __tablename__ = "approval_steps"
    __table_args__ = (
        UniqueConstraint("request_id", "step_no", name="uq_approval_step"),
    )
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("approval_requests.id"))
    step_no: Mapped[int] = mapped_column(Integer)
    required_role: Mapped[str] = mapped_column(String)
    scope_ref: Mapped[str | None] = mapped_column(String)
    resolved_approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String, default="PENDING")
    decision: Mapped[str | None] = mapped_column(String)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String)
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))  # SLA


class Exception_(Base, PKMixin, TimestampMixin):
    __tablename__ = "exceptions"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    category: Mapped[str] = mapped_column(String)  # models.enums.ExceptionCategory
    issue_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)  # models.enums.ExceptionSeverity
    summary: Mapped[str | None] = mapped_column(String)
    owner_role: Mapped[str | None] = mapped_column(String)
    evidence: Mapped[dict | None] = mapped_column(JSONB)  # feature-level reasons / links
    resolution_status: Mapped[str] = mapped_column(String, default="OPEN")  # OPEN|RESOLVED
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base, PKMixin, TimestampMixin):
    __tablename__ = "notifications"
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"))
    to_address: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # ACK | REMINDER | DIGEST | VENDOR
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
