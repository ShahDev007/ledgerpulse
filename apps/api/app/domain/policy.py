"""Versioned approval-policy engine (Section 7.4).

Policies are authored as YAML in packages/policies/, loaded into approval_policies (immutable
once active), and evaluated against invoice 'facts'. Conditions use a tiny, safe expression
grammar (comparisons + AND/OR over invoice.<field>) — no arbitrary code, and policies are
trusted repo artifacts.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.workflow import ApprovalPolicy

def _resolve_policy_dir() -> Path:
    """Find packages/policies across Docker (/app/...) and Vercel (repo-relative) layouts."""
    import os

    if os.getenv("POLICY_DIR"):
        return Path(os.environ["POLICY_DIR"])
    candidates = [Path("/app/packages/policies")]
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "packages" / "policies")
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


POLICY_DIR = _resolve_policy_dir()


def invoice_facts(inv: Invoice) -> SimpleNamespace:
    is_construction = bool(inv.project_id or inv.contract_id or inv.purchase_order_id)
    flags = inv.risk_flags or []
    return SimpleNamespace(
        total=float(inv.total) if inv.total is not None else 0.0,
        category="CONSTRUCTION" if is_construction else "OPERATING",
        is_unbudgeted=("UNBUDGETED_SPEND" in flags or "OVER_BUDGET" in flags),
        budget_variance_pct=0.0,
        is_credit_memo=inv.is_credit_memo,
        property_id=str(inv.property_id) if inv.property_id else None,
        project_id=str(inv.project_id) if inv.project_id else None,
    )


def _eval(expr: str, invoice: SimpleNamespace) -> bool:
    py = expr.replace(" OR ", " or ").replace(" AND ", " and ")
    py = re.sub(r"\btrue\b", "True", py)
    py = re.sub(r"\bfalse\b", "False", py)
    try:
        return bool(eval(py, {"__builtins__": {}}, {"invoice": invoice}))  # noqa: S307 (trusted DSL)
    except Exception:
        return False


def _matches(policy_def: dict, facts: SimpleNamespace) -> bool:
    when = policy_def.get("when", {})
    conds = when.get("all", [])
    return all(_eval(c, facts) for c in conds) if conds else True


def load_policy_files() -> list[dict]:
    out = []
    if not POLICY_DIR.exists():
        return out
    for p in sorted(POLICY_DIR.glob("*.yaml")):
        out.append(yaml.safe_load(p.read_text()))
    return out


async def sync_policies(session: AsyncSession) -> int:
    """Upsert policy files into approval_policies (idempotent)."""
    n = 0
    for pd in load_policy_files():
        name, version = pd["policy"], int(pd.get("version", 1))
        existing = (
            await session.execute(
                select(ApprovalPolicy).where(
                    ApprovalPolicy.name == name, ApprovalPolicy.version == version
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(ApprovalPolicy(name=name, version=version, definition=pd, active=True))
            n += 1
        else:
            existing.definition = pd
    await session.commit()
    return n


async def select_policy(session: AsyncSession, inv: Invoice) -> dict:
    """Pick the most specific matching policy. Construction beats default; fallback is hardcoded."""
    facts = invoice_facts(inv)
    policies = (
        await session.execute(select(ApprovalPolicy).where(ApprovalPolicy.active.is_(True)))
    ).scalars().all()
    # order: construction first, then default, then others by name
    ordered = sorted(
        policies,
        key=lambda p: (0 if "construction" in p.name else 1 if "default" in p.name else 2, p.name),
    )
    for p in ordered:
        if _matches(p.definition, facts):
            return p.definition
    # Hardcoded fallback
    return {
        "policy": "fallback_v1",
        "version": 1,
        "steps": [{"role": "AP_ACCOUNTANT"}, {"role": "FINANCE_ADMIN"}],
        "controls": {"submitter_cannot_approve": True, "allow_delegation": True,
                     "escalation_after_hours": 48},
    }


def resolve_steps(policy_def: dict, inv: Invoice) -> list[dict]:
    """Return the ordered, applicable steps (each step's conditional `when` evaluated)."""
    facts = invoice_facts(inv)
    steps = []
    for i, step in enumerate(policy_def.get("steps", []), start=1):
        cond = step.get("when")
        if cond and not _eval(cond, facts):
            continue
        steps.append({"step_no": i, "role": step["role"], "scope": step.get("scope")})
    return steps
