"""Celery application. Broker/result backend = Redis.

Task modules (extract, match, notify, export, payment_sync) are added in later phases and
registered here via `include`.
"""
from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "ledgerpulse",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "worker.tasks.ping",
        # Phase 3+: "worker.tasks.extract",
        # Phase 4+: "worker.tasks.match",
        # Phase 5+: "worker.tasks.notify", "worker.tasks.export",
        # Phase 7+: "worker.tasks.payment_sync",
    ],
)

app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
