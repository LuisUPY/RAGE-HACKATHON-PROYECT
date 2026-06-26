"""LLM client helpers (OpenAI-compatible APIs, e.g. NVIDIA NIM)."""

from rage_core.llm.openai_compat import (
    diagnose_llm_setup,
    format_llm_api_error,
    get_judge_model,
    get_llm_client,
    get_llm_model,
    has_llm_backend,
    llm_judge_enabled,
    sanitize_api_key,
    verify_llm_connection,
)

__all__ = [
    "diagnose_llm_setup",
    "format_llm_api_error",
    "get_llm_client",
    "get_llm_model",
    "get_judge_model",
    "has_llm_backend",
    "llm_judge_enabled",
    "sanitize_api_key",
    "verify_llm_connection",
]
