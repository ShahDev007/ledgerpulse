"""Deterministic seed ids so master data + demo invoices reference stable UUIDs.

Using UUIDv5 over a fixed namespace makes re-seeding idempotent and lets fixtures in
different phases point at the same property/vendor/GL without hard-coding literals.
"""
from __future__ import annotations

import uuid

SEED_NS = uuid.UUID("00000000-0000-0000-0000-00000000ca11")


def sid(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NS, key)
