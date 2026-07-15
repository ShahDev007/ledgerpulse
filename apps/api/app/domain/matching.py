"""Commercial matching (Section 7.2): PO, contract rate, work-order status, budget, arithmetic.

Returns explainable Findings; the pipeline turns them into MatchResults + Exceptions. Also
links the resolved PO / contract / work order onto the invoice.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field as dc_field
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commercial import Contract, ContractRate, PurchaseOrder, WorkOrder
from app.models.finance import BudgetLine, Budget
from app.models.invoice import Invoice, InvoiceLineItem

UNBUDGETED_THRESHOLD = Decimal("25000")


@dataclass
class Finding:
    kind: str            # match_results.kind: po|contract|work_order|budget|arithmetic
    outcome: str         # MATCH|REVIEW|BLOCK|NONE
    category: str        # exception category (COMMERCIAL|FINANCIAL|...)
    issue_type: str
    severity: str        # INFO|REVIEW|BLOCKING
    summary: str
    owner_role: str
    reasons: dict = dc_field(default_factory=dict)
    creates_exception: bool = True


async def match_commercial(session: AsyncSession, inv: Invoice) -> list[Finding]:
    findings: list[Finding] = []

    # --- PO match ---
    if inv.po_number_text:
        po = (
            await session.execute(
                select(PurchaseOrder).where(PurchaseOrder.number == inv.po_number_text.strip())
            )
        ).scalar_one_or_none()
        if po:
            inv.purchase_order_id = po.id
            inv.project_id = inv.project_id or po.project_id
            over = inv.total is not None and inv.total > (po.open_amount or Decimal("0"))
            findings.append(
                Finding(
                    kind="po", outcome="REVIEW" if over else "MATCH",
                    category="COMMERCIAL", issue_type="PO_OVER_COMMITMENT",
                    severity="REVIEW", owner_role="CONSTRUCTION_PM",
                    summary=f"Invoice {inv.total} exceeds PO {po.number} open amount {po.open_amount}"
                    if over else f"Matched PO {po.number}",
                    reasons={"po_number": po.number, "open_amount": str(po.open_amount),
                             "invoice_total": str(inv.total)},
                    creates_exception=over,
                )
            )

    # --- Contract rate check ---
    if inv.vendor_id and inv.property_id:
        contract = (
            await session.execute(
                select(Contract).where(
                    Contract.vendor_id == inv.vendor_id, Contract.property_id == inv.property_id
                )
            )
        ).scalar_one_or_none()
        if contract:
            inv.contract_id = contract.id
            rates = (
                await session.execute(
                    select(ContractRate).where(ContractRate.contract_id == contract.id)
                )
            ).scalars().all()
            lines = (
                await session.execute(
                    select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == inv.id)
                )
            ).scalars().all()
            for ln in lines:
                if ln.unit_price is None or not ln.description:
                    continue
                for rate in rates:
                    if fuzz.token_set_ratio(ln.description, rate.description) >= 80:
                        ceiling = rate.unit_rate * (1 + (rate.tolerance_pct or Decimal("0")) / 100)
                        if ln.unit_price > ceiling:
                            findings.append(
                                Finding(
                                    kind="contract", outcome="REVIEW",
                                    category="COMMERCIAL", issue_type="RATE_ABOVE_CONTRACT",
                                    severity="REVIEW", owner_role="CONSTRUCTION_PM",
                                    summary=(f"Line '{ln.description[:40]}' billed {ln.unit_price}/unit "
                                             f"exceeds contract rate {rate.unit_rate} (+{rate.tolerance_pct}%)"),
                                    reasons={"line": ln.description, "billed": str(ln.unit_price),
                                             "contract_rate": str(rate.unit_rate),
                                             "tolerance_pct": str(rate.tolerance_pct)},
                                )
                            )
                        break

    # --- Work order status ---
    if inv.work_order_text:
        wo = (
            await session.execute(
                select(WorkOrder).where(WorkOrder.number == inv.work_order_text.strip())
            )
        ).scalar_one_or_none()
        if wo:
            inv.work_order_id = wo.id
            if wo.status in ("CLOSED", "CANCELLED"):
                findings.append(
                    Finding(
                        kind="work_order", outcome="REVIEW",
                        category="COMMERCIAL", issue_type="WORK_ORDER_CLOSED",
                        severity="REVIEW", owner_role="PROPERTY_MANAGER",
                        summary=f"Work order {wo.number} is {wo.status}; invoice billed against it",
                        reasons={"work_order": wo.number, "status": wo.status},
                    )
                )

    # --- Budget check (large / capital spend) ---
    if inv.total is not None and inv.total >= UNBUDGETED_THRESHOLD and inv.property_id:
        q = select(BudgetLine).join(Budget, BudgetLine.budget_id == Budget.id).where(
            Budget.property_id == inv.property_id
        )
        lines = (await session.execute(q)).scalars().all()
        if not lines:
            findings.append(
                Finding(
                    kind="budget", outcome="REVIEW",
                    category="FINANCIAL", issue_type="UNBUDGETED_SPEND",
                    severity="REVIEW", owner_role="ASSET_MANAGER",
                    summary=f"No budget found for this property; {inv.total} is unbudgeted",
                    reasons={"invoice_total": str(inv.total), "budget_lines": 0},
                )
            )
        else:
            remaining = sum(
                (bl.revised_budget or Decimal("0")) - (bl.committed or Decimal("0")) - (bl.actual or Decimal("0"))
                for bl in lines
            )
            if inv.total > remaining:
                findings.append(
                    Finding(
                        kind="budget", outcome="REVIEW",
                        category="FINANCIAL", issue_type="OVER_BUDGET",
                        severity="REVIEW", owner_role="ASSET_MANAGER",
                        summary=f"Invoice {inv.total} exceeds remaining budget {remaining}",
                        reasons={"invoice_total": str(inv.total), "remaining": str(remaining)},
                    )
                )

    # --- Arithmetic check ---
    if inv.subtotal is not None and inv.total is not None:
        expected = (inv.subtotal or Decimal("0")) + (inv.tax or Decimal("0"))
        if abs(expected - inv.total) > Decimal("0.01"):
            findings.append(
                Finding(
                    kind="arithmetic", outcome="REVIEW",
                    category="FINANCIAL", issue_type="ARITHMETIC_MISMATCH",
                    severity="REVIEW", owner_role="AP_ACCOUNTANT",
                    summary=f"subtotal+tax ({expected}) != total ({inv.total})",
                    reasons={"subtotal": str(inv.subtotal), "tax": str(inv.tax), "total": str(inv.total)},
                )
            )

    return findings
