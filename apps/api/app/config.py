"""Application settings (pydantic-settings), sourced from the environment."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_async_url() -> str:
    """Prefer DATABASE_URL; otherwise derive an asyncpg URL from Vercel Postgres env vars."""
    url = os.getenv("DATABASE_URL")
    if not url:
        # Vercel/Neon provide POSTGRES_URL (libpq form); prefer the non-pooling one for DDL.
        url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    if not url:
        return "postgresql+asyncpg://ledgerpulse:ledgerpulse@postgres:5432/ledgerpulse"
    # Normalize scheme to asyncpg and strip libpq-only query params (sslmode) asyncpg rejects.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    url = url.split("?", 1)[0]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = "local"
    auth_secret: str = "dev-only-change-me"
    admin_token: str = "dev-admin-token"

    database_url: str = _resolve_async_url()
    database_url_sync: str = "postgresql+psycopg://ledgerpulse:ledgerpulse@postgres:5432/ledgerpulse"
    redis_url: str = "redis://redis:6379/0"

    @property
    def serverless(self) -> bool:
        return bool(os.getenv("VERCEL"))

    @property
    def db_needs_ssl(self) -> bool:
        # Managed Postgres (Neon/Vercel) requires TLS; local Docker does not.
        return self.serverless or "neon.tech" in self.database_url or "vercel-storage" in self.database_url

    s3_endpoint_url: str = "http://minio:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = "ledgerpulse"
    s3_secret_key: str = "ledgerpulse-secret"
    s3_bucket: str = "ledgerpulse-invoices"

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    ap_inbox_address: str = "invoices@ledgerpulse.local"
    mock_erp_url: str = "http://mock-erp:4010"


@lru_cache
def get_settings() -> Settings:
    return Settings()
