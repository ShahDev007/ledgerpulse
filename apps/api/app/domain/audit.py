"""Append-only, hash-chained audit log (Section 8.3).

Each event stores previous_event_hash → event_hash, forming a tamper-evident chain. The chain
is global (single ledger) for the demo; production could shard per-entity. Hashing is stable
(sorted JSON) so the chain is verifiable offline.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_audit import AuditEvent


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def _hash(previous: str | None, payload: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update((previous or "").encode())
    h.update(_canonical(payload).encode())
    return "sha256:" + h.hexdigest()


async def record_audit(
    session: AsyncSession,
    *,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    entity_version: int | None = None,
    actor_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
    evidence_ids: list[str] | None = None,
    model_run_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    """Append one audit event, chained to the most recent event's hash.

    Must be called within the same transaction as the state change it records.
    """
    prev = (
        await session.execute(
            select(AuditEvent.event_hash).order_by(AuditEvent.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    body = {
        "actor_type": actor_type,
        "actor_id": actor_id,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "entity_version": entity_version,
        "action": action,
        "before": before,
        "after": after,
        "reason": reason,
        "evidence_ids": evidence_ids,
        "model_run_id": str(model_run_id) if model_run_id else None,
        "request_id": request_id,
    }
    event = AuditEvent(
        actor_type=actor_type,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=entity_version,
        action=action,
        before=before,
        after=after,
        reason=reason,
        evidence_ids=evidence_ids,
        model_run_id=model_run_id,
        request_id=request_id,
        previous_event_hash=prev,
        event_hash=_hash(prev, body),
    )
    session.add(event)
    return event
