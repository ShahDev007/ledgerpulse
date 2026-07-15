"""Seed master data + demo personas (idempotent).

Demo invoices (INV-001..008) are seeded by app.seed_invoices in later phases; this module
establishes the organization, properties, vendors, GL/cost codes, and one user per persona.

Run:  python -m app.seed          (upsert)
      python -m app.seed --reset  (drop + recreate + reseed via bootstrap)
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.ids import sid
from app.models.commercial import (
    Contract,
    ContractRate,
    CostCode,
    Project,
    PurchaseOrder,
    WorkOrder,
)
from app.models.enums import Role
from app.models.finance import Budget, BudgetLine, GLAccount
from app.models.identity import User
from app.models.organization import LegalEntity, Property, Unit
from app.models.organization import Organization
from app.models.vendor import Vendor, VendorAlias

ORG_ID = sid("org:cadence-demo")

# --- Static master-data definitions ----------------------------------------
PROPERTIES = [
    ("prop_park", "Park & Parkside", "PARK", "1200 Park Ave, Seattle, WA"),
    ("prop_cedar", "Cedar Commons", "CEDAR", "88 Cedar St, Seattle, WA"),
    ("prop_maple", "Maplewood Flats", "MAPLE", "455 Maple Blvd, Bellevue, WA"),
]

VENDORS = [
    ("ven_nwplumbing", "Northwest Plumbing LLC", ["NW Plumbing", "Northwest Plumbing"], "ACTIVE", True, True),
    ("ven_cascade", "Cascade Electric Utility", ["Cascade Electric", "Cascade Power"], "ACTIVE", True, True),
    ("ven_evergreen", "Evergreen Landscaping", ["Evergreen Lawn Care"], "ACTIVE", True, False),
    ("ven_summit", "Summit General Contractors", ["Summit GC", "Summit Construction"], "ACTIVE", True, True),
]

GL_ACCOUNTS = [
    ("gl_repairs_plumbing", "6100", "Repairs-Plumbing", "OPEX"),
    ("gl_utilities_electric", "6200", "Utilities-Electric", "OPEX"),
    ("gl_landscaping", "6300", "Landscaping", "OPEX"),
    ("gl_construction_cip", "1700", "Construction in Progress", "CAPEX"),
    ("gl_repairs_general", "6000", "Repairs-General", "OPEX"),
]

COST_CODES = [
    ("cc_plumbing", "03-100", "Plumbing"),
    ("cc_electrical", "03-200", "Electrical"),
    ("cc_sitework", "02-100", "Sitework / Landscaping"),
]

# Scope shapes each persona's view (ABAC). Operational roles are narrowed to the
# properties/projects they run; control roles (AP, Finance, Director, Auditor) are org-wide
# on purpose - a controller or auditor with a partial view would be wrong.
PERSONAS = [
    ("ap@ledgerpulse.local", "Alex Park (AP Accountant)", Role.AP_ACCOUNTANT, None),  # org-wide
    ("pm@ledgerpulse.local", "Priya Nair (Property Manager)", Role.PROPERTY_MANAGER, ["prop_park"]),
    ("cpm@ledgerpulse.local", "Chris Reyes (Construction PM)", Role.CONSTRUCTION_PM, ["prop_maple"]),
    ("asset@ledgerpulse.local", "Sam Ito (Asset Manager)", Role.ASSET_MANAGER, ["prop_cedar", "prop_maple"]),
    ("finadmin@ledgerpulse.local", "Dana Lee (Finance Admin)", Role.FINANCE_ADMIN, None),  # org-wide
    ("director@ledgerpulse.local", "Morgan Blake (Director of Finance)", Role.DIRECTOR_FINANCE, None),  # org-wide
    ("auditor@ledgerpulse.local", "Jordan Cole (Auditor)", Role.AUDITOR, None),  # org-wide
]


async def _upsert(session: AsyncSession, model, id_, defaults: dict):
    obj = await session.get(model, id_)
    if obj is None:
        obj = model(id=id_, **defaults)
        session.add(obj)
    else:
        for k, v in defaults.items():
            setattr(obj, k, v)
    return obj


async def seed(reset: bool = False) -> None:
    async with SessionLocal() as session:
        # Organization + one legal entity
        await _upsert(session, Organization, ORG_ID, {"name": "Cadence Demo", "slug": "cadence-demo"})
        await _upsert(
            session, LegalEntity, sid("le:main"),
            {"organization_id": ORG_ID, "name": "Cadence Demo Holdings LLC", "code": "CDH"},
        )

        for key, name, code, addr in PROPERTIES:
            await _upsert(
                session, Property, sid(key),
                {"organization_id": ORG_ID, "legal_entity_id": sid("le:main"),
                 "name": name, "code": code, "address": addr},
            )
        # A couple of units at Park & Parkside
        for label in ("204", "118"):
            await _upsert(
                session, Unit, sid(f"unit:park:{label}"),
                {"property_id": sid("prop_park"), "label": label},
            )

        for key, name, aliases, status, w9, ins in VENDORS:
            await _upsert(
                session, Vendor, sid(key),
                {"organization_id": ORG_ID, "canonical_name": name, "display_name": name,
                 "status": status, "has_w9": w9, "has_insurance": ins},
            )
            for alias in aliases:
                await _upsert(
                    session, VendorAlias, sid(f"alias:{key}:{alias}"),
                    {"vendor_id": sid(key), "alias": alias},
                )

        for key, code, name, capex in GL_ACCOUNTS:
            await _upsert(
                session, GLAccount, sid(key),
                {"organization_id": ORG_ID, "code": code, "name": name, "default_capex_opex": capex},
            )

        for key, code, name in COST_CODES:
            await _upsert(
                session, CostCode, sid(key),
                {"organization_id": ORG_ID, "code": code, "name": name},
            )

        # One renovation project + a couple of work orders (used by matching scenarios)
        await _upsert(
            session, Project, sid("proj_park_reno"),
            {"property_id": sid("prop_park"), "name": "Park & Parkside Value-Add Renovation",
             "code": "PARK-RENO", "status": "ACTIVE"},
        )
        await _upsert(
            session, WorkOrder, sid("wo_8841"),
            {"property_id": sid("prop_park"), "unit_id": sid("unit:park:204"),
             "vendor_id": sid("ven_nwplumbing"), "number": "WO-8841",
             "category": "Plumbing", "description": "Replace leaking supply line - Unit 204",
             "status": "OPEN"},
        )
        await _upsert(
            session, WorkOrder, sid("wo_closed"),
            {"property_id": sid("prop_cedar"), "vendor_id": sid("ven_nwplumbing"),
             "number": "WO-7710", "category": "Plumbing", "description": "Faucet repair",
             "status": "CLOSED"},
        )

        # Commercial context for matching scenarios (INV-002, INV-006)
        await _upsert(
            session, PurchaseOrder, sid("po_3477"),
            {"property_id": sid("prop_park"), "project_id": sid("proj_park_reno"),
             "vendor_id": sid("ven_summit"), "number": "PO-3477",
             "amount": Decimal("25000.00"), "open_amount": Decimal("25000.00"), "status": "OPEN"},
        )
        await _upsert(
            session, Contract, sid("contract_summit_park"),
            {"property_id": sid("prop_park"), "project_id": sid("proj_park_reno"),
             "vendor_id": sid("ven_summit"), "number": "CT-SUM-01",
             "ceiling": Decimal("200000.00")},
        )
        # Contract rate the invoice will exceed (invoice bills 980.00/unit vs 900.00 contract)
        await _upsert(
            session, ContractRate, sid("rate_cabinetry"),
            {"contract_id": sid("contract_summit_park"),
             "description": "Unit renovation - kitchen cabinetry",
             "unit_rate": Decimal("900.00"), "tolerance_pct": Decimal("2.0")},
        )
        # Park renovation is budgeted; Maplewood has no budget → INV-006 capital is unbudgeted.
        await _upsert(
            session, Budget, sid("budget_park_reno"),
            {"property_id": sid("prop_park"), "project_id": sid("proj_park_reno"),
             "name": "Park & Parkside Renovation Budget"},
        )
        await _upsert(
            session, BudgetLine, sid("budgetline_park_reno"),
            {"budget_id": sid("budget_park_reno"), "cost_code_id": sid("cc_plumbing"),
             "original_budget": Decimal("200000.00"), "revised_budget": Decimal("200000.00"),
             "committed": Decimal("25000.00"), "actual": Decimal("10000.00")},
        )

        # Personas
        for email, name, role, prop_keys in PERSONAS:
            scope = [sid(k) for k in prop_keys] if prop_keys else None
            await _upsert(
                session, User, sid(f"user:{email}"),
                {"organization_id": ORG_ID, "email": email, "full_name": name,
                 "role": role.value, "active": True, "property_scope": scope,
                 "approval_limit": Decimal("100000")},
            )

        await session.commit()

        # Load approval policies from packages/policies/*.yaml
        from app.domain.policy import sync_policies

        n = await sync_policies(session)
        print(f"[seed] master data + {len(PERSONAS)} personas + {n} policies ready")


if __name__ == "__main__":
    asyncio.run(seed(reset="--reset" in sys.argv))
