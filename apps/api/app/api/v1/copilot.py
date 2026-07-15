"""Evidence-grounded, permission-filtered copilot endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, get_principal
from app.db import get_session
from app.domain.copilot import run_copilot

router = APIRouter(tags=["copilot"])


class CopilotIn(BaseModel):
    question: str


@router.post("/copilot/query")
async def copilot_query(
    body: CopilotIn,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    principal.require("view")
    return await run_copilot(session, principal, body.question)
