"""Persona-based auth for the demo.

Seeded users each have a Role; the frontend "switches persona" by requesting a signed
session token for that user. RBAC capabilities are derived from Role. ABAC scope
(property/project) lives on the User row and is enforced in query filters + retrieval.

This is deliberately simple (dev JWT). The production path is Entra ID / OIDC + MFA + SCIM.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models.enums import Role
from app.models.identity import User

ALGO = "HS256"

# RBAC capability matrix (Section 8.2). Capabilities:
#   view, edit, approve, export, admin_policy, admin_integration, view_audit, view_model_trace
_CAP = {
    Role.AP_ACCOUNTANT: {"view", "edit", "export", "view_model_trace"},
    Role.PROPERTY_MANAGER: {"view", "approve"},
    Role.CONSTRUCTION_PM: {"view", "approve"},
    Role.ASSET_MANAGER: {"view", "approve", "view_model_trace"},
    Role.FINANCE_ADMIN: {"view", "edit", "approve", "export", "admin_policy", "view_audit", "view_model_trace"},
    Role.DIRECTOR_FINANCE: {"view", "approve", "export", "admin_policy", "view_audit", "view_model_trace"},
    Role.AUDITOR: {"view", "view_audit", "view_model_trace"},
}


def capabilities_for(role: str) -> set[str]:
    try:
        return _CAP[Role(role)]
    except (ValueError, KeyError):
        return {"view"}


@dataclass
class Principal:
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    capabilities: set[str]
    property_scope: list[uuid.UUID] | None
    project_scope: list[uuid.UUID] | None
    approval_limit: float | None

    def require(self, capability: str) -> None:
        if capability not in self.capabilities:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {self.role} lacks capability '{capability}'",
            )


def issue_token(user: User) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=12),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=ALGO)


async def get_principal(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.auth_secret, algorithms=[ALGO])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Unknown or inactive user")
    return Principal(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        capabilities=capabilities_for(user.role),
        property_scope=user.property_scope,
        project_scope=user.project_scope,
        approval_limit=float(user.approval_limit) if user.approval_limit is not None else None,
    )
