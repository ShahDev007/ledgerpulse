"""Invoice intake, inbox list, detail (digital twin), and original-file download."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import get_session
from app.domain.correction import apply_field_correction
from app.domain.extraction import run_extraction
from app.domain.invoice import intake_invoice
from app.domain.investigator import run_investigation
from app.domain.pipeline import process_invoice
from app.models.ai_audit import AuditEvent, MatchResult, ModelRun
from app.models.enums import SourceType
from app.models.invoice import FieldProvenance, Invoice, InvoiceFile, InvoiceLineItem
from app.models.workflow import Exception_
from app.storage import get_blob

router = APIRouter(tags=["invoices"])

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/heic", "image/webp"}
MAX_BYTES = 20 * 1024 * 1024


class IntakeOut(BaseModel):
    invoice_id: str
    tracking_id: str
    status: str
    exact_duplicate_of: str | None = None


@router.post("/invoices/intake", response_model=IntakeOut, status_code=201)
async def intake(
    file: UploadFile = File(...),
    property_hint: str | None = Form(default=None),
    vendor_hint: str | None = Form(default=None),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("edit")
    data = await file.read()
    if len(data) == 0 or len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File empty or exceeds 20MB limit")
    ctype = file.content_type or "application/octet-stream"
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {ctype}")

    result = await intake_invoice(
        session,
        file_bytes=data,
        filename=file.filename or "upload.bin",
        content_type=ctype,
        source_type=SourceType.UPLOAD,
        raw_vendor_hint=vendor_hint,
        property_hint=property_hint,
        actor_id=str(principal.user_id),
    )
    return IntakeOut(
        invoice_id=str(result.invoice_id),
        tracking_id=result.tracking_id,
        status="RECEIVED",
        exact_duplicate_of=str(result.duplicate_of) if result.duplicate_of else None,
    )


@router.post("/invoices/{invoice_id}/extract", response_model=IntakeOut)
async def extract(
    invoice_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Run live Claude extraction on the immutable original and persist the digital twin."""
    principal.require("edit")
    inv = await run_extraction(session, invoice_id, actor_id=str(principal.user_id))
    return IntakeOut(invoice_id=str(inv.id), tracking_id=inv.tracking_id, status=inv.status)


@router.post("/invoices/{invoice_id}/match", response_model=IntakeOut)
async def match(
    invoice_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Re-run resolution + duplicate/commercial/budget matching + risk."""
    principal.require("edit")
    inv = await process_invoice(session, invoice_id)
    return IntakeOut(invoice_id=str(inv.id), tracking_id=inv.tracking_id, status=inv.status)


@router.post("/invoices/{invoice_id}/investigate")
async def investigate_exception(
    invoice_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Run the read-only exception investigator agent (Claude Opus) on the open exception."""
    principal.require("view")
    return await run_investigation(session, invoice_id, actor_id=str(principal.user_id))


class InvoiceRow(BaseModel):
    id: str
    tracking_id: str
    status: str
    source_type: str
    vendor: str | None
    invoice_number: str | None
    total: float | None
    currency: str
    risk_score: float
    risk_flags: list[str]
    created_at: str


@router.get("/invoices", response_model=list[InvoiceRow])
async def list_invoices(
    status: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    limit: int = 100,
):
    principal.require("view")
    q = select(Invoice).order_by(Invoice.created_at.desc()).limit(min(limit, 500))
    if status:
        q = q.where(Invoice.status == status)
    if principal.property_scope:
        q = q.where(
            (Invoice.property_id.in_(principal.property_scope)) | (Invoice.property_id.is_(None))
        )
    rows = (await session.execute(q)).scalars().all()
    return [
        InvoiceRow(
            id=str(i.id),
            tracking_id=i.tracking_id,
            status=i.status,
            source_type=i.source_type,
            vendor=i.resolved_vendor_name or i.raw_vendor_name,
            invoice_number=i.invoice_number,
            total=float(i.total) if i.total is not None else None,
            currency=i.currency,
            risk_score=float(i.risk_score),
            risk_flags=i.risk_flags or [],
            created_at=i.created_at.isoformat(),
        )
        for i in rows
    ]


class TimelineEvent(BaseModel):
    occurred_at: str
    actor_type: str
    action: str
    reason: str | None
    event_hash: str


class InvoiceDetail(BaseModel):
    id: str
    tracking_id: str
    status: str
    source_type: str
    lock_version: int
    vendor: str | None
    invoice_number: str | None
    invoice_date: str | None
    due_date: str | None
    currency: str
    subtotal: float | None
    tax: float | None
    total: float | None
    document_hash: str | None
    risk_score: float
    risk_flags: list[str]
    is_credit_memo: bool
    resolved_vendor: str | None
    resolved_property: str | None
    extraction_confidence: float | None
    field_confidence: dict[str, float]
    files: list[dict]
    lines: list[dict]
    model_runs: list[dict]
    exceptions: list[dict]
    match_results: list[dict]
    timeline: list[TimelineEvent]


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
async def invoice_detail(
    invoice_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    files = (
        await session.execute(select(InvoiceFile).where(InvoiceFile.invoice_id == invoice_id))
    ).scalars().all()
    lines = (
        await session.execute(
            select(InvoiceLineItem)
            .where(InvoiceLineItem.invoice_id == invoice_id)
            .order_by(InvoiceLineItem.line_no)
        )
    ).scalars().all()
    events = (
        await session.execute(
            select(AuditEvent)
            .where(AuditEvent.entity_id == invoice_id)
            .order_by(AuditEvent.created_at.asc())
        )
    ).scalars().all()
    prov = (
        await session.execute(
            select(FieldProvenance).where(FieldProvenance.invoice_id == invoice_id)
        )
    ).scalars().all()
    runs = (
        await session.execute(
            select(ModelRun)
            .where(ModelRun.invoice_id == invoice_id)
            .order_by(ModelRun.created_at.asc())
        )
    ).scalars().all()

    field_confidence = {
        p.field_name: float(p.confidence) for p in prov if p.confidence is not None
    }
    excs = (
        await session.execute(
            select(Exception_)
            .where(Exception_.invoice_id == invoice_id)
            .order_by(Exception_.created_at.desc())
        )
    ).scalars().all()
    matches = (
        await session.execute(
            select(MatchResult)
            .where(MatchResult.invoice_id == invoice_id)
            .order_by(MatchResult.created_at.desc())
        )
    ).scalars().all()

    return InvoiceDetail(
        id=str(inv.id),
        tracking_id=inv.tracking_id,
        status=inv.status,
        source_type=inv.source_type,
        lock_version=inv.lock_version,
        vendor=inv.raw_vendor_name,
        invoice_number=inv.invoice_number,
        invoice_date=inv.invoice_date.isoformat() if inv.invoice_date else None,
        due_date=inv.due_date.isoformat() if inv.due_date else None,
        currency=inv.currency,
        subtotal=float(inv.subtotal) if inv.subtotal is not None else None,
        tax=float(inv.tax) if inv.tax is not None else None,
        total=float(inv.total) if inv.total is not None else None,
        document_hash=inv.document_hash,
        risk_score=float(inv.risk_score),
        risk_flags=inv.risk_flags or [],
        is_credit_memo=inv.is_credit_memo,
        resolved_vendor=inv.resolved_vendor_name,
        resolved_property=inv.resolved_property_name,
        extraction_confidence=float(inv.extraction_confidence)
        if inv.extraction_confidence is not None
        else None,
        field_confidence=field_confidence,
        model_runs=[
            {
                "capability": r.capability,
                "provider": r.provider,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "latency_ms": r.latency_ms,
                "cost_usd": float(r.cost_usd) if r.cost_usd is not None else None,
                "status": r.status,
            }
            for r in runs
        ],
        exceptions=[
            {
                "id": str(e.id),
                "category": e.category,
                "issue_type": e.issue_type,
                "severity": e.severity,
                "summary": e.summary,
                "owner_role": e.owner_role,
                "status": e.resolution_status,
                "evidence": e.evidence,
            }
            for e in excs
        ],
        match_results=[
            {
                "kind": m.kind,
                "outcome": m.outcome,
                "score": float(m.score) if m.score is not None else None,
                "reasons": m.reasons,
            }
            for m in matches
        ],
        files=[
            {
                "id": str(f.id),
                "filename": f.storage_key.rsplit("/", 1)[-1],
                "content_type": f.content_type,
                "byte_size": f.byte_size,
                "sha256": f.sha256,
                "is_original": f.is_original,
            }
            for f in files
        ],
        lines=[
            {
                "line_no": ln.line_no,
                "description": ln.description,
                "quantity": float(ln.quantity) if ln.quantity is not None else None,
                "unit_price": float(ln.unit_price) if ln.unit_price is not None else None,
                "amount": float(ln.amount) if ln.amount is not None else None,
            }
            for ln in lines
        ],
        timeline=[
            TimelineEvent(
                occurred_at=e.created_at.isoformat(),
                actor_type=e.actor_type,
                action=e.action,
                reason=e.reason,
                event_hash=e.event_hash,
            )
            for e in events
        ],
    )


@router.get("/invoices/{invoice_id}/file")
async def download_file(
    invoice_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    f = (
        await session.execute(
            select(InvoiceFile)
            .where(InvoiceFile.invoice_id == invoice_id, InvoiceFile.is_original.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="File not found")
    data = await get_blob(session, f.storage_key)
    return Response(content=data, media_type=f.content_type)


class FieldPatch(BaseModel):
    field: str
    value: str | None = None
    lock_version: int


class FieldPatchOut(BaseModel):
    field: str
    old_value: str | None
    new_value: str | None
    lock_version: int


@router.patch("/invoices/{invoice_id}/fields", response_model=FieldPatchOut)
async def correct_field(
    invoice_id: uuid.UUID,
    patch: FieldPatch,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Optimistic-locked field correction → feedback label + audit event."""
    principal.require("edit")
    r = await apply_field_correction(
        session,
        invoice_id,
        field=patch.field,
        value=patch.value,
        expected_lock_version=patch.lock_version,
        actor_id=str(principal.user_id),
    )
    return FieldPatchOut(
        field=r.field, old_value=r.old_value, new_value=r.new_value, lock_version=r.lock_version
    )
