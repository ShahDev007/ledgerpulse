"""Transactional outbox helper.

emit() writes a row to the outbox table inside the caller's transaction. A separate relay
(worker.tasks, Phase 2+) publishes unpublished rows to Redis and marks them published, so an
event is never lost even if the process crashes after commit.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_audit import Outbox


async def emit(session: AsyncSession, topic: str, payload: dict[str, Any]) -> Outbox:
    row = Outbox(topic=topic, payload=payload, published=False)
    session.add(row)
    return row
