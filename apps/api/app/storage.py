"""Pluggable object storage for immutable invoice files.

STORAGE_BACKEND selects the backend:
  - "postgres" (default on Vercel/hosted): bytes live in the invoice_blobs table — no external
    object store, works anywhere Postgres does.
  - "s3": MinIO/S3 via boto3 (local Docker default).

The Postgres backend needs the request's AsyncSession; the S3 backend ignores it.
"""
from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

BACKEND = os.getenv("STORAGE_BACKEND", "s3").lower()


# --- S3 / MinIO ---
def _s3_client():
    import boto3
    from botocore.config import Config

    s = get_settings()
    return boto3.client(
        "s3", endpoint_url=s.s3_endpoint_url, aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key, region_name=s.s3_region,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def ensure_bucket() -> None:
    if BACKEND != "s3":
        return
    s = get_settings()
    client = _s3_client()
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
    if s.s3_bucket not in existing:
        client.create_bucket(Bucket=s.s3_bucket)


# --- unified async API ---
async def put_blob(session: AsyncSession, key: str, data: bytes, content_type: str) -> None:
    if BACKEND == "postgres":
        from app.models.invoice import InvoiceBlob

        session.add(InvoiceBlob(storage_key=key, content_type=content_type, data=data))
        await session.flush()
    else:
        import asyncio

        await asyncio.to_thread(
            lambda: _s3_client().put_object(
                Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=content_type
            )
        )


async def get_blob(session: AsyncSession, key: str) -> bytes:
    if BACKEND == "postgres":
        from app.models.invoice import InvoiceBlob

        row = (
            await session.execute(select(InvoiceBlob).where(InvoiceBlob.storage_key == key))
        ).scalar_one_or_none()
        if row is None:
            raise FileNotFoundError(key)
        return bytes(row.data)
    import asyncio

    def _get():
        return _s3_client().get_object(Bucket=get_settings().s3_bucket, Key=key)["Body"].read()

    return await asyncio.to_thread(_get)
