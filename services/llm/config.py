"""LLM/embedding provider settings, read from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class LLMSettings:
    provider: str  # "mock" | "anthropic"
    anthropic_api_key: str | None
    model_classify: str
    model_extract: str
    model_extract_escalate: str
    model_coding: str
    model_investigator: str
    model_copilot: str
    ocr_provider: str  # "mock" | "azure" | "textract"
    embedding_provider: str  # "mock" | "voyage"
    embedding_dim: int
    voyage_api_key: str | None
    voyage_model: str
    timeout_seconds: int
    max_retries: int
    daily_token_budget: int

    @property
    def anthropic_enabled(self) -> bool:
        return self.provider == "anthropic" and bool(self.anthropic_api_key)


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings(
        provider=os.getenv("LLM_PROVIDER", "mock").lower(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model_classify=os.getenv("LLM_MODEL_CLASSIFY", "claude-haiku-4-5-20251001"),
        model_extract=os.getenv("LLM_MODEL_EXTRACT", "claude-sonnet-5"),
        model_extract_escalate=os.getenv("LLM_MODEL_EXTRACT_ESCALATE", "claude-opus-4-8"),
        model_coding=os.getenv("LLM_MODEL_CODING", "claude-sonnet-5"),
        model_investigator=os.getenv("LLM_MODEL_INVESTIGATOR", "claude-opus-4-8"),
        model_copilot=os.getenv("LLM_MODEL_COPILOT", "claude-sonnet-5"),
        ocr_provider=os.getenv("OCR_PROVIDER", "mock").lower(),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "mock").lower(),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
        voyage_api_key=os.getenv("VOYAGE_API_KEY") or None,
        voyage_model=os.getenv("VOYAGE_MODEL", "voyage-3-large"),
        timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        daily_token_budget=int(os.getenv("LLM_DAILY_TOKEN_BUDGET", "2000000")),
    )
