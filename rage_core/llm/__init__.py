"""LLM client helpers (OpenAI API and Ollama-compatible endpoints)."""

from rage_core.llm.openai_compat import (
    get_judge_model,
    get_llm_client,
    get_llm_model,
    has_llm_backend,
    llm_judge_enabled,
)

__all__ = [
    "get_llm_client",
    "get_llm_model",
    "get_judge_model",
    "has_llm_backend",
    "llm_judge_enabled",
]
