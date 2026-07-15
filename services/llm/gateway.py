"""LLM gateway - the single, provider-neutral entry point for model calls.

Enforces schema-constrained output (Anthropic tool use), timeouts, bounded retries, and
captures a ModelRunInfo (provider, model, tokens, latency) for the model_runs ledger. When
LLM_PROVIDER != anthropic or no key is present, falls back to a deterministic mock so the app
still runs offline and CI/golden evals stay stable.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import Any

from services.llm.config import LLMSettings, get_llm_settings
from services.llm.prompts import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SYSTEM,
    EXTRACTION_USER,
)
from services.llm.schemas import InvoiceExtraction

# --- JSON schema for the extraction tool (strings everywhere; domain layer coerces) --------
_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "page": {"type": ["integer", "null"]},
        "bbox": {"type": ["array", "null"], "items": {"type": "number"}},
        "raw_text": {"type": ["string", "null"]},
    },
    "required": ["value", "confidence"],
}
_LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "description": _FIELD_SCHEMA,
        "quantity": _FIELD_SCHEMA,
        "unit_price": _FIELD_SCHEMA,
        "amount": _FIELD_SCHEMA,
    },
}
EXTRACTION_TOOL = {
    "name": "emit_invoice",
    "description": "Return the structured extraction of the accounting document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "enum": ["invoice", "credit_memo", "statement", "receipt", "other"],
            },
            "vendor_name": _FIELD_SCHEMA,
            "invoice_number": _FIELD_SCHEMA,
            "invoice_date": _FIELD_SCHEMA,
            "due_date": _FIELD_SCHEMA,
            "property_hint": _FIELD_SCHEMA,
            "purchase_order_number": _FIELD_SCHEMA,
            "work_order_number": _FIELD_SCHEMA,
            "subtotal": _FIELD_SCHEMA,
            "tax": _FIELD_SCHEMA,
            "total": _FIELD_SCHEMA,
            "currency": _FIELD_SCHEMA,
            "lines": {"type": "array", "items": _LINE_SCHEMA},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["document_type", "vendor_name", "total"],
    },
}


RESOLVE_TOOL = {
    "name": "pick_entity",
    "description": "Pick the single best matching entity id, or null if none is a confident match.",
    "input_schema": {
        "type": "object",
        "properties": {
            "match_id": {"type": ["string", "null"]},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["match_id", "confidence", "reason"],
    },
}


@dataclass
class ResolveResult:
    match_id: str | None
    confidence: float
    reason: str
    provider: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


def resolve_entity(
    raw_name: str,
    candidates: list[dict],
    *,
    kind: str = "vendor",
    context: str = "",
    settings: LLMSettings | None = None,
) -> ResolveResult:
    """Claude reasons over the allow-listed candidate list and picks the best id (or null)."""
    s = settings or get_llm_settings()
    if not s.anthropic_enabled:
        return ResolveResult(match_id=None, confidence=0.0, reason="mock: no resolution", provider="mock")

    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=s.timeout_seconds)
    listing = "\n".join(
        f"- id={c['id']} name={c['name']!r} aliases={c.get('aliases', [])}" for c in candidates
    )
    system = (
        f"You match a raw {kind} string from an invoice to one of the allow-listed {kind} "
        f"records. Only pick a candidate you are confident is the same real-world {kind}. "
        f"If none matches, return match_id=null. Never invent an id outside the list."
    )
    user = f"Raw {kind}: {raw_name!r}\n{context}\nCandidates:\n{listing}\n\nUse pick_entity."
    t0 = time.monotonic()
    try:
        resp = client.messages.create(
            model=s.model_coding, max_tokens=300, system=system,
            tools=[RESOLVE_TOOL], tool_choice={"type": "tool", "name": "pick_entity"},
            messages=[{"role": "user", "content": user}],
        )
        tu = next((b for b in resp.content if b.type == "tool_use"), None)
        data = dict(tu.input) if tu else {"match_id": None, "confidence": 0.0, "reason": "no tool"}
        valid_ids = {c["id"] for c in candidates}
        mid = data.get("match_id")
        if mid not in valid_ids:
            mid = None  # guard against hallucinated ids
        return ResolveResult(
            match_id=mid,
            confidence=float(data.get("confidence", 0.0)),
            reason=str(data.get("reason", "")),
            provider="anthropic", model=resp.model,
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as exc:  # noqa: BLE001
        return ResolveResult(match_id=None, confidence=0.0, reason=f"error: {exc}", provider="anthropic")


@dataclass
class ModelRunInfo:
    provider: str
    model: str | None
    prompt_version: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    status: str = "OK"
    error: str | None = None
    raw_output: dict[str, Any] | None = None


@dataclass
class ExtractionOutcome:
    extraction: InvoiceExtraction
    run: ModelRunInfo
    warnings: list[str] = field(default_factory=list)


def _content_block(file_bytes: bytes, content_type: str) -> dict:
    b64 = base64.standard_b64encode(file_bytes).decode()
    if content_type == "application/pdf":
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": content_type, "data": b64},
    }


def _mock_extraction() -> InvoiceExtraction:
    return InvoiceExtraction.model_validate(
        {
            "document_type": "invoice",
            "vendor_name": {"value": None, "confidence": 0.0},
            "invoice_number": {"value": None, "confidence": 0.0},
            "invoice_date": {"value": None, "confidence": 0.0},
            "due_date": {"value": None, "confidence": 0.0},
            "property_hint": {"value": None, "confidence": 0.0},
            "purchase_order_number": {"value": None, "confidence": 0.0},
            "subtotal": {"value": None, "confidence": 0.0},
            "tax": {"value": None, "confidence": 0.0},
            "total": {"value": None, "confidence": 0.0},
            "currency": {"value": "USD", "confidence": 0.5},
            "lines": [],
            "warnings": ["mock provider - set LLM_PROVIDER=anthropic with a key for live extraction"],
        }
    )


def extract_invoice(
    file_bytes: bytes,
    content_type: str,
    *,
    properties: list[str] | None = None,
    vendors: list[str] | None = None,
    settings: LLMSettings | None = None,
) -> ExtractionOutcome:
    s = settings or get_llm_settings()

    if not s.anthropic_enabled:
        return ExtractionOutcome(
            extraction=_mock_extraction(),
            run=ModelRunInfo(provider="mock", model=None, prompt_version=EXTRACTION_PROMPT_VERSION),
        )

    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=s.timeout_seconds)
    user_text = EXTRACTION_USER.format(
        properties=", ".join(properties or []) or "(none provided)",
        vendors=", ".join(vendors or []) or "(none provided)",
    )
    messages = [
        {
            "role": "user",
            "content": [
                _content_block(file_bytes, content_type),
                {"type": "text", "text": user_text},
            ],
        }
    ]

    last_err: Exception | None = None
    for attempt in range(1, s.max_retries + 1):
        t0 = time.monotonic()
        try:
            resp = client.messages.create(
                model=s.model_extract,
                max_tokens=2000,
                system=EXTRACTION_SYSTEM,
                tools=[EXTRACTION_TOOL],
                tool_choice={"type": "tool", "name": "emit_invoice"},
                messages=messages,
            )
            latency = int((time.monotonic() - t0) * 1000)
            tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
            if tool_use is None:
                raise ValueError("model did not return the emit_invoice tool call")
            extraction = InvoiceExtraction.model_validate(tool_use.input)
            run = ModelRunInfo(
                provider="anthropic",
                model=resp.model,
                prompt_version=EXTRACTION_PROMPT_VERSION,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                latency_ms=latency,
                raw_output=dict(tool_use.input),
            )
            return ExtractionOutcome(
                extraction=extraction, run=run, warnings=extraction.warnings
            )
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < s.max_retries:
                time.sleep(min(2 ** attempt * 0.5, 4))

    # Retries exhausted → deterministic fallback so the pipeline degrades gracefully.
    return ExtractionOutcome(
        extraction=_mock_extraction(),
        run=ModelRunInfo(
            provider="anthropic",
            model=s.model_extract,
            prompt_version=EXTRACTION_PROMPT_VERSION,
            status="ERROR",
            error=str(last_err)[:500] if last_err else "unknown",
        ),
        warnings=[f"extraction failed after retries: {last_err}"],
    )
