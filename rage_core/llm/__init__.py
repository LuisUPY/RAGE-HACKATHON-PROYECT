"""LLM client helpers (OpenAI API and Ollama-compatible endpoints)."""

from rage_core.llm.openai_compat import (
    diagnose_llm_setup,
    get_judge_model,
    get_llm_client,
    get_llm_model,
    has_llm_backend,
    llm_judge_enabled,
)

__all__ = [
    "diagnose_llm_setup",
    "get_llm_client",
    "get_llm_model",
    "get_judge_model",
    "has_llm_backend",
    "llm_judge_enabled",
]
