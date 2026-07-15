"""LLM gateway: provider-neutral, schema-constrained, evidence-logged access to Claude.

The gateway is the ONLY path application code uses to reach a model. It enforces
schema-constrained output, timeouts/retries/circuit-breaking, redaction, tool
allow-lists, and model-run logging. Providers (mock, anthropic) are swapped by env.
"""

from services.llm.config import LLMSettings, get_llm_settings
from services.llm.schemas import (
    ExtractedField,
    ExtractedInvoiceLine,
    InvoiceExtraction,
    CodingCandidate,
    CodingRecommendation,
    InvestigatorResult,
)

__all__ = [
    "LLMSettings",
    "get_llm_settings",
    "ExtractedField",
    "ExtractedInvoiceLine",
    "InvoiceExtraction",
    "CodingCandidate",
    "CodingRecommendation",
    "InvestigatorResult",
]
