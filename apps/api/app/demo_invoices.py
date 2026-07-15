"""Synthetic invoice documents for the 8 demo scenarios (Appendix A.6).

Renders realistic invoice PNGs with PIL so live Claude extraction has genuine content to read
(no hardcoded 'expected' shortcut). All data is fabricated — no real vendors or company data.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont


@dataclass
class LineSpec:
    description: str
    quantity: str
    unit_price: str
    amount: str


@dataclass
class InvoiceSpec:
    key: str  # INV-001..008
    vendor: str
    remit_to: str
    invoice_number: str
    invoice_date: str
    due_date: str
    bill_to_property: str
    service_address: str
    po_number: str | None
    work_order: str | None
    lines: list[LineSpec]
    subtotal: str
    tax: str
    total: str
    is_credit_memo: bool = False
    note: str = ""
    # scenario metadata (used by seeding/matching, not drawn)
    scenario: str = ""


SPECS: list[InvoiceSpec] = [
    InvoiceSpec(
        key="INV-001", vendor="Cascade Electric Utility",
        remit_to="PO Box 4400, Seattle, WA 98101",
        invoice_number="CE-100582", invoice_date="2026-07-02", due_date="2026-07-25",
        bill_to_property="Park & Parkside", service_address="1200 Park Ave, Seattle, WA",
        po_number=None, work_order=None,
        lines=[LineSpec("Electricity service - June 2026 (common areas)", "1", "1240.50", "1240.50")],
        subtotal="1240.50", tax="0.00", total="1240.50",
        scenario="clean recurring utility",
    ),
    InvoiceSpec(
        key="INV-002", vendor="Summit General Contractors",
        remit_to="900 Industrial Way, Kent, WA 98032",
        invoice_number="SUM-2041", invoice_date="2026-07-05", due_date="2026-08-04",
        bill_to_property="Park & Parkside", service_address="1200 Park Ave, Seattle, WA",
        po_number="PO-3477", work_order=None,
        lines=[
            LineSpec("Unit renovation - kitchen cabinetry (12 units)", "12", "980.00", "11760.00"),
            LineSpec("Flooring install - LVP (per unit)", "12", "560.00", "6720.00"),
        ],
        subtotal="18480.00", tax="0.00", total="18480.00",
        note="Rate on cabinetry exceeds contract rate of 900.00/unit",
        scenario="construction, one rate above contract",
    ),
    InvoiceSpec(
        key="INV-003", vendor="Cascade Electric Utility",
        remit_to="PO Box 4400, Seattle, WA 98101",
        invoice_number="CE-1OO582", invoice_date="2026-07-02", due_date="2026-07-25",
        bill_to_property="Park & Parkside", service_address="1200 Park Ave, Seattle, WA",
        po_number=None, work_order=None,
        lines=[LineSpec("Electricity service - June 2026 (common areas)", "1", "1240.50", "1240.50")],
        subtotal="1240.50", tax="0.00", total="1240.50",
        note="Invoice number O/0 variant of CE-100582",
        scenario="duplicate of INV-001 (O/0 variant)",
    ),
    InvoiceSpec(
        key="INV-004", vendor="Rainier Roofing Co",
        remit_to="55 Summit Ridge, Tacoma, WA 98402",
        invoice_number="RR-8890", invoice_date="2026-07-06", due_date="2026-08-05",
        bill_to_property="Cedar Commons", service_address="88 Cedar St, Seattle, WA",
        po_number=None, work_order=None,
        lines=[LineSpec("Emergency roof leak repair - Building B", "1", "3450.00", "3450.00")],
        subtotal="3450.00", tax="0.00", total="3450.00",
        note="Vendor not in master data",
        scenario="unknown vendor",
    ),
    InvoiceSpec(
        key="INV-005", vendor="Northwest Plumbing LLC",
        remit_to="120 Trade St, Seattle, WA 98108",
        invoice_number="NP-10590", invoice_date="2026-07-07", due_date="2026-07-30",
        bill_to_property="Cedar Commons", service_address="88 Cedar St, Seattle, WA",
        po_number=None, work_order="WO-7710",
        lines=[LineSpec("Faucet repair - Unit 12", "1", "285.00", "285.00")],
        subtotal="285.00", tax="0.00", total="285.00",
        note="Work order WO-7710 is closed",
        scenario="repair tied to closed work order",
    ),
    InvoiceSpec(
        key="INV-006", vendor="Summit General Contractors",
        remit_to="900 Industrial Way, Kent, WA 98032",
        invoice_number="SUM-2075", invoice_date="2026-07-09", due_date="2026-08-08",
        bill_to_property="Maplewood Flats", service_address="455 Maple Blvd, Bellevue, WA",
        po_number=None, work_order=None,
        lines=[LineSpec("New rooftop HVAC units - capital improvement", "2", "31000.00", "62000.00")],
        subtotal="62000.00", tax="0.00", total="62000.00",
        note="Unbudgeted capital improvement above threshold",
        scenario="unbudgeted capital > threshold",
    ),
    InvoiceSpec(
        key="INV-007", vendor="Cascade Electric Utility",
        remit_to="PO Box 4400, Seattle, WA 98101",
        invoice_number="CE-100582-CM", invoice_date="2026-07-10", due_date="2026-07-10",
        bill_to_property="Park & Parkside", service_address="1200 Park Ave, Seattle, WA",
        po_number=None, work_order=None,
        lines=[LineSpec("Credit - overbilled electricity, ref CE-100582", "1", "-120.00", "-120.00")],
        subtotal="-120.00", tax="0.00", total="-120.00",
        is_credit_memo=True, note="Credit memo referencing INV-001",
        scenario="credit memo referencing INV-001",
    ),
    InvoiceSpec(
        key="INV-008", vendor="Evergreen Landscaping",
        remit_to="77 Greenway Dr, Renton, WA 98057",
        invoice_number="EL-4521", invoice_date="2026-07-03", due_date="2026-07-26",
        bill_to_property="Park & Parkside", service_address="1200 Park Ave, Seattle, WA",
        po_number=None, work_order=None,
        lines=[LineSpec("Monthly landscaping service - July 2026", "1", "1650.00", "1650.00")],
        subtotal="1650.00", tax="0.00", total="1650.00",
        note="Will show partial payment mismatch after export",
        scenario="exported invoice w/ partial payment mismatch",
    ),
]

SPEC_BY_KEY = {s.key: s for s in SPECS}


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def render_png(spec: InvoiceSpec) -> bytes:
    W, H = 1000, 1300
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    navy = (18, 41, 74)
    teal = (18, 126, 122)
    gray = (90, 90, 90)

    f_title = _font(40)
    f_h = _font(24)
    f = _font(20)
    f_sm = _font(16)

    # Header
    d.rectangle([0, 0, W, 90], fill=navy)
    title = "CREDIT MEMO" if spec.is_credit_memo else "INVOICE"
    d.text((40, 25), title, font=f_title, fill="white")
    d.text((40, 110), spec.vendor, font=f_h, fill=teal)
    d.text((40, 145), f"Remit to: {spec.remit_to}", font=f_sm, fill=gray)

    # Meta block (right)
    x = 620
    rows = [
        ("Invoice #", spec.invoice_number),
        ("Invoice date", spec.invoice_date),
        ("Due date", spec.due_date),
    ]
    if spec.po_number:
        rows.append(("PO #", spec.po_number))
    if spec.work_order:
        rows.append(("Work Order", spec.work_order))
    y = 110
    for label, val in rows:
        d.text((x, y), f"{label}:", font=f_sm, fill=gray)
        d.text((x + 130, y), val, font=f, fill=navy)
        y += 30

    # Bill-to
    d.text((40, 210), "Bill To:", font=f_sm, fill=gray)
    d.text((40, 235), spec.bill_to_property, font=f_h, fill=navy)
    d.text((40, 268), f"Service address: {spec.service_address}", font=f_sm, fill=gray)

    # Line items table
    ty = 340
    d.rectangle([40, ty, W - 40, ty + 34], fill=(235, 240, 247))
    d.text((50, ty + 7), "Description", font=f_sm, fill=navy)
    d.text((640, ty + 7), "Qty", font=f_sm, fill=navy)
    d.text((720, ty + 7), "Unit Price", font=f_sm, fill=navy)
    d.text((880, ty + 7), "Amount", font=f_sm, fill=navy)
    ty += 44
    for ln in spec.lines:
        d.text((50, ty), ln.description, font=f_sm, fill=(30, 30, 30))
        d.text((640, ty), ln.quantity, font=f_sm, fill=(30, 30, 30))
        d.text((720, ty), ln.unit_price, font=f_sm, fill=(30, 30, 30))
        d.text((880, ty), ln.amount, font=f_sm, fill=(30, 30, 30))
        ty += 34

    # Totals
    ty += 20
    for label, val in [("Subtotal", spec.subtotal), ("Tax", spec.tax), ("Total", spec.total)]:
        bold = label == "Total"
        d.text((720, ty), label, font=(f if bold else f_sm), fill=navy)
        d.text((880, ty), f"{val}", font=(f if bold else f_sm), fill=(navy if bold else (30, 30, 30)))
        ty += 32

    d.text((40, H - 60), "Thank you for your business.", font=f_sm, fill=gray)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
