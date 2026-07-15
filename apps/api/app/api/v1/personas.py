"""Persona directory + session issuance for the demo persona switcher."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import capabilities_for, issue_token
from app.db import get_session
from app.models.identity import User

router = APIRouter(tags=["personas"])


class PersonaOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    capabilities: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    persona: PersonaOut


@router.get("/personas", response_model=list[PersonaOut])
async def list_personas(session: AsyncSession = Depends(get_session)):
    users = (await session.execute(select(User).order_by(User.full_name))).scalars().all()
    return [
        PersonaOut(
            id=str(u.id), email=u.email, full_name=u.full_name, role=u.role,
            capabilities=sorted(capabilities_for(u.role)),
        )
        for u in users
    ]


@router.post("/personas/{persona_id}/session", response_model=TokenOut)
async def switch_persona(persona_id: str, session: AsyncSession = Depends(get_session)):
    import uuid

    user = await session.get(User, uuid.UUID(persona_id))
    if user is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return TokenOut(
        access_token=issue_token(user),
        persona=PersonaOut(
            id=str(user.id), email=user.email, full_name=user.full_name, role=user.role,
            capabilities=sorted(capabilities_for(user.role)),
        ),
    )
