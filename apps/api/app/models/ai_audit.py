"""AI + audit: model runs, tool calls, match results, anomaly flags, feedback labels,
append-only audit events (hash-chained), and the transactional outbox + processed ledger."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PKMixin, TimestampMixin


class ModelRun(Base, PKMixin, TimestampMixin):
    __tablename__ = "model_runs"
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"))
    capability: Mapped[str] = mapped_column(String)  # extract|classify|coding|investigator|copilot
    provider: Mapped[str] = mapped_column(String)  # mock|anthropic
    model: Mapped[str | None] = mapped_column(String)
    prompt_version: Mapped[str | None] = mapped_column(String)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    status: Mapped[str] = mapped_column(String, default="OK")  # OK|ERROR
    output: Mapped[dict | None] = mapped_column(JSONB)


class ToolCall(Base, PKMixin, TimestampMixin):
    __tablename__ = "tool_calls"
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id"))
    tool_name: Mapped[str] = mapped_column(String)
    arguments: Mapped[dict | None] = mapped_column(JSONB)
    result_summary: Mapped[str | None] = mapped_column(String)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)


class MatchResult(Base, PKMixin, TimestampMixin):
    __tablename__ = "match_results"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    kind: Mapped[str] = mapped_column(String)  # duplicate|po|contract|work_order|budget
    score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    outcome: Mapped[str] = mapped_column(String)  # MATCH|REVIEW|BLOCK|NONE
    reasons: Mapped[dict | None] = mapped_column(JSONB)  # feature-level breakdown
    related_id: Mapped[uuid.UUID | None] = mapped_column()


class AnomalyFlag(Base, PKMixin, TimestampMixin):
    __tablename__ = "anomaly_flags"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    kind: Mapped[str] = mapped_column(String)
    detail: Mapped[str | None] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Numeric(5, 4))


class FeedbackLabel(Base, PKMixin, TimestampMixin):
    """Every correction is a labeled event, not an overwritten prediction (Section 4.5)."""
    __tablename__ = "feedback_labels"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    field_name: Mapped[str] = mapped_column(String)
    predicted: Mapped[dict | None] = mapped_column(JSONB)
    corrected: Mapped[dict | None] = mapped_column(JSONB)
    corrected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    do_not_learn: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditEvent(Base, PKMixin, TimestampMixin):
    """Append-only, hash-chained audit log (Section 8.3)."""
    __tablename__ = "audit_events"
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actor_type: Mapped[str] = mapped_column(String)  # USER|RULE|MODEL|INTEGRATION|SYSTEM
    actor_id: Mapped[str | None] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    entity_version: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(String)
    evidence_ids: Mapped[list | None] = mapped_column(JSONB)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_runs.id"))
    request_id: Mapped[str | None] = mapped_column(String)
    previous_event_hash: Mapped[str | None] = mapped_column(String)
    event_hash: Mapped[str] = mapped_column(String, index=True)


class Outbox(Base, PKMixin, TimestampMixin):
    """Transactional outbox: events written in the same tx as the state change."""
    __tablename__ = "outbox"
    topic: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(Base, PKMixin, TimestampMixin):
    """Idempotent-consumer ledger: (consumer, event_id) processed once."""
    __tablename__ = "processed_events"
    consumer: Mapped[str] = mapped_column(String)
    event_id: Mapped[str] = mapped_column(String, index=True)
