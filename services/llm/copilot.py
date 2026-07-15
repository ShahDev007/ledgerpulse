"""Evidence-grounded copilot: answer NL questions over a permission-filtered data context.

The model receives ONLY the rows the caller is allowed to see (built by the domain layer) and
must ground its answer in them, citing invoice tracking ids. It is a view over controlled data,
never a replacement for the ledger — no tools, no mutations.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from services.llm.config import LLMSettings, get_llm_settings

ANSWER_TOOL = {
    "name": "answer",
    "description": "Answer the question grounded only in the provided data. Cite invoice tracking ids.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "cited_tracking_ids": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
            "insufficient_data": {"type": "boolean"},
        },
        "required": ["answer", "cited_tracking_ids", "confidence"],
    },
}

SYSTEM = """You are LedgerPulse Copilot. Answer ONLY from the provided JSON data context, which
has already been filtered to what this user is permitted to see. Do not invent invoices, vendors,
or numbers not present. Cite the invoice tracking ids you used. If the data is insufficient, say so
and set insufficient_data=true. Be concise and specific with amounts and statuses."""


@dataclass
class CopilotOutcome:
    result: dict | None
    provider: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    status: str = "OK"
    error: str | None = None


def answer_question(question: str, context: dict, *, settings: LLMSettings | None = None) -> CopilotOutcome:
    s = settings or get_llm_settings()
    if not s.anthropic_enabled:
        return CopilotOutcome(
            result={"answer": "Copilot requires live Claude (set LLM_PROVIDER=anthropic).",
                    "cited_tracking_ids": [], "confidence": 0.0, "insufficient_data": True},
            provider="mock", status="SKIPPED",
        )
    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=s.timeout_seconds)
    user = f"Question: {question}\n\nData context (JSON):\n{json.dumps(context, default=str)}"
    t0 = time.monotonic()
    try:
        resp = client.messages.create(
            model=s.model_copilot, max_tokens=1000, system=SYSTEM,
            tools=[ANSWER_TOOL], tool_choice={"type": "tool", "name": "answer"},
            messages=[{"role": "user", "content": user}],
        )
        tu = next((b for b in resp.content if b.type == "tool_use"), None)
        return CopilotOutcome(
            result=dict(tu.input) if tu else None, provider="anthropic", model=resp.model,
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as exc:  # noqa: BLE001
        return CopilotOutcome(result=None, provider="anthropic", status="ERROR", error=str(exc)[:300])
