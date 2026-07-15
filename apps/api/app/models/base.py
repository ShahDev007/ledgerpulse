"""Common column mixins: UUIDv7 primary keys and UTC timestamps.

UUIDv7 is time-ordered (RFC 9562), which keeps primary keys roughly insertion-ordered
for good index locality while remaining globally unique. Implemented inline to avoid a
fragile third-party dependency.
"""
from __future__ import annotations

import datetime as dt
import os
import time
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def uuid7() -> uuid.UUID:
    """Generate a UUIDv7 (48-bit ms timestamp + 74 bits randomness)."""
    unix_ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits, we use 74
    # Layout: 48-bit ts | ver(4) | 12 rand | var(2) | 62 rand
    uint = (unix_ms & 0xFFFFFFFFFFFF) << 80
    uint |= (0x7 << 76)
    uint |= ((rand >> 68) & 0xFFF) << 64
    uint |= (0b10 << 62)
    uint |= rand & 0x3FFFFFFFFFFFFFFF
    return uuid.UUID(int=uint)


def new_id() -> uuid.UUID:
    return uuid7()


class PKMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
