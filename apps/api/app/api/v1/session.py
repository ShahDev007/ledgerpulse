"""Current-principal introspection ('who am I + what can I do')."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import Principal, get_principal

router = APIRouter(tags=["session"])


class MeOut(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    capabilities: list[str]


@router.get("/me", response_model=MeOut)
async def me(principal: Principal = Depends(get_principal)):
    return MeOut(
        user_id=str(principal.user_id),
        email=principal.email,
        full_name=principal.full_name,
        role=principal.role,
        capabilities=sorted(principal.capabilities),
    )
