"""Risk scoring (Section 7.3): combine vendor/document/commercial/duplicate signals."""
from __future__ import annotations

from decimal import Decimal

from app.domain.duplicate import DuplicateFinding
from app.domain.matching import Finding
from app.domain.resolution import ResolutionOutcome
from app.models.invoice import Invoice


def compute_risk(
    inv: Invoice,
    resolution: ResolutionOutcome,
    duplicate: DuplicateFinding,
    commercial: list[Finding],
) -> tuple[float, list[str]]:
    score = 0.0
    flags: list[str] = []

    if not resolution.vendor_resolved:
        score += 0.35
        flags.append("UNKNOWN_VENDOR")
    if not resolution.property_resolved:
        score += 0.10
        flags.append("UNRESOLVED_PROPERTY")

    if inv.extraction_confidence is not None and float(inv.extraction_confidence) < 0.90:
        score += 0.10
        flags.append("LOW_EXTRACTION_CONFIDENCE")

    if duplicate.outcome == "BLOCK":
        score += 0.45
        flags.append("POSSIBLE_DUPLICATE")
    elif duplicate.outcome == "REVIEW":
        score += 0.25
        flags.append("POSSIBLE_DUPLICATE")

    for f in commercial:
        if f.issue_type == "RATE_ABOVE_CONTRACT":
            score += 0.20
            flags.append("RATE_ABOVE_CONTRACT")
        elif f.issue_type in ("UNBUDGETED_SPEND", "OVER_BUDGET"):
            score += 0.20
            flags.append(f.issue_type)
        elif f.issue_type == "WORK_ORDER_CLOSED":
            score += 0.15
            flags.append("WORK_ORDER_CLOSED")
        elif f.issue_type == "PO_OVER_COMMITMENT":
            score += 0.15
            flags.append("PO_OVER_COMMITMENT")
        elif f.issue_type == "ARITHMETIC_MISMATCH":
            score += 0.15
            flags.append("ARITHMETIC_MISMATCH")

    return min(round(score, 4), 1.0), sorted(set(flags))
