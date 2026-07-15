"""Async SQLAlchemy 2 engine/session + declarative Base."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# On serverless (Vercel), pooling across invocations causes stale connections - use NullPool and
# a fresh connection per request; managed Postgres (Neon) requires TLS.
_engine_kwargs: dict = {"echo": False}
_connect_args: dict = {}
if settings.serverless:
    _engine_kwargs["poolclass"] = NullPool
    # Disable asyncpg prepared-statement cache so we survive even if a pgbouncer (pooled)
    # URL slips through - pgbouncer transaction pooling breaks server-side prepared statements.
    _connect_args["statement_cache_size"] = 0
else:
    _engine_kwargs["pool_pre_ping"] = True
if settings.db_needs_ssl:
    _connect_args["ssl"] = True
if _connect_args:
    _engine_kwargs["connect_args"] = _connect_args

engine = create_async_engine(settings.database_url, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request."""
    async with SessionLocal() as session:
        yield session
