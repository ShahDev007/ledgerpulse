"""Golden model-eval: live Claude extraction accuracy on the synthetic invoices.

Skipped unless LLM_PROVIDER=anthropic + a key is present (extraction is non-deterministic, so
this is a model eval, not a unit test). Measures header-field exact accuracy against expected
values and enforces a threshold (Section 10.3).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.demo_invoices import SPECS, render_png
from app.domain.normalize import normalize_invoice_number, parse_decimal
from services.llm.config import get_llm_settings
from services.llm.gateway import extract_invoice

pytestmark = pytest.mark.skipif(
    not get_llm_settings().anthropic_enabled,
    reason="live Claude not configured (LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY)",
)

HEADER_THRESHOLD = 0.94  # >= 94% header-field exact accuracy overall (Section 10.3)


def test_header_field_accuracy_meets_threshold():
    correct = total = 0
    misses: list[str] = []
    for spec in SPECS:
        png = render_png(spec)
        ex = extract_invoice(png, "image/png",
                             properties=[spec.bill_to_property], vendors=[spec.vendor]).extraction
        checks = {
            "vendor": (ex.vendor_name.value or "").strip().lower() == spec.vendor.lower(),
            "invoice_number": normalize_invoice_number(ex.invoice_number.value)
            == normalize_invoice_number(spec.invoice_number),
            "total": parse_decimal(ex.total.value) == Decimal(spec.total),
        }
        for field, ok in checks.items():
            total += 1
            correct += int(ok)
            if not ok:
                misses.append(f"{spec.key}.{field}={getattr(ex, 'vendor_name' if field=='vendor' else field).value!r}")
    accuracy = correct / total
    assert accuracy >= HEADER_THRESHOLD, f"header accuracy {accuracy:.2%} < {HEADER_THRESHOLD:.0%}; misses={misses}"
