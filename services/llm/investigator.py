"""Read-only exception investigator agent (Section 4.3, Appendix A.5).

A tool-scoped Claude (Opus) agent that runs ONLY when an exception exists. It is given a
fixed, read-only tool allow-list backed by a pre-loaded evidence snapshot — the model cannot
reach the database, mutate records, send mail, approve, export, or pay. It gathers evidence and
must cite evidence ids for material claims, then calls submit_findings with the structured
result. Prohibited tools simply do not exist in its tool list.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from services.llm.config import LLMSettings, get_llm_settings

# Read-only tools (no arguments — all scoped to the single invoice under investigation).
_READ_TOOLS = [
    ("get_invoice", "Header fields + resolved links for this invoice."),
    ("get_document_evidence", "Field-level provenance (page/bbox/confidence) captured at extraction."),
    ("search_duplicate_candidates", "Duplicate scoring + the best candidate with feature breakdown."),
    ("get_vendor_history", "Other invoices from the same vendor."),
    ("get_purchase_order", "Linked purchase order, if any."),
    ("get_contract", "Linked contract + contract rates, if any."),
    ("get_work_order", "Linked work order + status, if any."),
    ("get_budget_status", "Budget lines + remaining for the property/project."),
    ("get_approval_policy", "The approval policy that would apply."),
]

SUBMIT_TOOL = {
    "name": "submit_findings",
    "description": "Return the final structured investigation result. Cite evidence ids.",
    "input_schema": {
        "type": "object",
        "properties": {
            "issue_type": {"type": "string"},
            "severity": {"type": "string", "enum": ["INFO", "REVIEW", "BLOCKING"]},
            "summary": {"type": "string"},
            "confirmed_facts": {"type": "array", "items": {"type": "string"}},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "recommended_action": {"type": "string"},
            "requested_information": {"type": "array", "items": {"type": "string"}},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
            "draft_message": {"type": ["string", "null"]},
        },
        "required": ["issue_type", "severity", "summary", "recommended_action",
                     "evidence_ids", "confidence"],
    },
}

SYSTEM = """You are a read-only accounts-payable exception investigator for a single invoice.
You may ONLY use the provided read tools; you cannot modify records, send messages, approve,
export, or release payment. Gather the evidence you need, run comparisons, and identify the
issue. Every material factual claim in confirmed_facts must reference an evidence id returned by
a tool (ids look like 'ev:invoice', 'ev:duplicate', 'ev:contract', ...). State uncertainties and
what human information is still needed. Do not invent data not present in tool results. When
finished, call submit_findings. You may draft (not send) a vendor or internal message."""

TOOL_SPECS = [
    {"name": n, "description": d, "input_schema": {"type": "object", "properties": {}}}
    for n, d in _READ_TOOLS
]


@dataclass
class ToolCallLog:
    tool_name: str
    result_summary: str
    allowed: bool = True


@dataclass
class InvestigationOutcome:
    result: dict | None
    provider: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    tool_calls: list[ToolCallLog] = field(default_factory=list)
    status: str = "OK"
    error: str | None = None


def investigate(
    snapshot: dict, issue_type: str, issue_summary: str, *, settings: LLMSettings | None = None
) -> InvestigationOutcome:
    s = settings or get_llm_settings()
    if not s.anthropic_enabled:
        return InvestigationOutcome(result=None, provider="mock", status="SKIPPED",
                                    error="anthropic disabled")

    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=s.timeout_seconds)
    tools = TOOL_SPECS + [SUBMIT_TOOL]
    messages = [{
        "role": "user",
        "content": f"Investigate this exception on the invoice.\nIssue type: {issue_type}\n"
                   f"Summary: {issue_summary}\nUse the read tools to gather evidence, then submit_findings.",
    }]
    logs: list[ToolCallLog] = []
    tin = tout = 0
    t0 = time.monotonic()

    for _ in range(10):  # bounded agent loop
        resp = client.messages.create(
            model=s.model_investigator, max_tokens=2000, system=SYSTEM,
            tools=tools, messages=messages,
        )
        tin += resp.usage.input_tokens
        tout += resp.usage.output_tokens
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            break
        messages.append({"role": "assistant", "content": resp.content})

        results = []
        finished = None
        for tu in tool_uses:
            if tu.name == "submit_findings":
                finished = dict(tu.input)
                logs.append(ToolCallLog("submit_findings", "final result"))
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": "ok"})
            elif tu.name in {t[0] for t in _READ_TOOLS}:
                data = snapshot.get(tu.name, {"note": "no data"})
                logs.append(ToolCallLog(tu.name, json.dumps(data)[:200]))
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": json.dumps(data, default=str)})
            else:  # prohibited / unknown tool — refuse
                logs.append(ToolCallLog(tu.name, "DENIED: tool not allowed", allowed=False))
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": "ERROR: tool not permitted", "is_error": True})
        if finished is not None:
            return InvestigationOutcome(
                result=finished, provider="anthropic", model=resp.model,
                input_tokens=tin, output_tokens=tout,
                latency_ms=int((time.monotonic() - t0) * 1000), tool_calls=logs,
            )
        messages.append({"role": "user", "content": results})

    return InvestigationOutcome(
        result=None, provider="anthropic", model=s.model_investigator,
        input_tokens=tin, output_tokens=tout,
        latency_ms=int((time.monotonic() - t0) * 1000), tool_calls=logs,
        status="ERROR", error="agent did not submit findings",
    )
