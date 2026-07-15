"""Trivial liveness task to prove the broker + worker wiring in Phase 1."""
from __future__ import annotations

from worker.celery_app import app


@app.task(name="ping")
def ping() -> str:
    return "pong"
