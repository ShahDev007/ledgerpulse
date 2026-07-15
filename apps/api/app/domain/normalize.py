"""Value normalization shared by extraction (Phase 3) and matching (Phase 4)."""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

# Common OCR confusions folded into a canonical form for duplicate-number matching.
_OCR_MAP = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"})


def normalize_invoice_number(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)   # drop punctuation/whitespace
    s = s.translate(_OCR_MAP)          # fold OCR-confusable chars
    s = s.lstrip("0") or "0"           # drop leading zeros
    return s


def parse_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        s = str(value).replace(",", "").replace("$", "").strip()
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def parse_date(value: object) -> dt.date | None:
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
