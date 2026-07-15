"""Deterministic-core unit tests: normalization, policy DSL, risk scoring.

These are pure functions (no DB / no network), so they run fast and gate every commit.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.domain.normalize import normalize_invoice_number, parse_date, parse_decimal
from app.domain.policy import _eval
from app.domain.risk import compute_risk


# --- invoice-number normalization (drives O/0 duplicate matching) ---
def test_normalize_folds_ocr_and_punctuation():
    assert normalize_invoice_number("CE-1OO582") == normalize_invoice_number("CE-100582")
    assert normalize_invoice_number("CE-100582") == "CE100582"
    assert normalize_invoice_number("  np 10482 ") == "NP10482"
    assert normalize_invoice_number(None) is None


def test_parse_helpers():
    assert parse_decimal("$1,825.00") == Decimal("1825.00")
    assert parse_decimal("-120.00") == Decimal("-120.00")
    assert parse_decimal("") is None
    assert parse_date("2026-07-02").isoformat() == "2026-07-02"
    assert parse_date("07/02/2026").isoformat() == "2026-07-02"
    assert parse_date("nope") is None


# --- approval-policy condition evaluator ---
def test_policy_eval_comparisons_and_boolean_ops():
    facts = SimpleNamespace(total=62000.0, category="CONSTRUCTION", is_unbudgeted=True,
                            budget_variance_pct=0.0)
    assert _eval("invoice.total >= 5000", facts) is True
    assert _eval("invoice.category == 'CONSTRUCTION'", facts) is True
    assert _eval("invoice.total >= 50000 OR invoice.is_unbudgeted == true", facts) is True
    assert _eval("invoice.budget_variance_pct > 5 OR invoice.total >= 25000", facts) is True
    assert _eval("invoice.total < 5000", facts) is False


def test_policy_eval_is_sandboxed():
    # Non-invoice references / arbitrary code must not evaluate truthy.
    facts = SimpleNamespace(total=1.0)
    assert _eval("__import__('os').system('echo hi') == 0", facts) is False


# --- risk scoring ---
def _inv(**kw):
    base = dict(extraction_confidence=Decimal("0.99"), risk_flags=[])
    base.update(kw)
    return SimpleNamespace(**base)


def test_risk_unknown_vendor_and_blocking_duplicate():
    res = SimpleNamespace(vendor_resolved=False, property_resolved=True)
    dup = SimpleNamespace(outcome="BLOCK")
    score, flags = compute_risk(_inv(), res, dup, [])
    assert "UNKNOWN_VENDOR" in flags and "POSSIBLE_DUPLICATE" in flags
    assert score >= 0.7


def test_risk_clean_invoice_is_low():
    res = SimpleNamespace(vendor_resolved=True, property_resolved=True)
    dup = SimpleNamespace(outcome="NONE")
    score, flags = compute_risk(_inv(), res, dup, [])
    assert score == 0.0 and flags == []
