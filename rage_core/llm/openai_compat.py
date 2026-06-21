"""
OpenAI-compatible LLM client for RAGE.

Primary backend: NVIDIA NIM — https://build.nvidia.com
  RAGE_LLM_BASE_URL  = https://integrate.api.nvidia.com/v1
  RAGE_LLM_API_KEY   = nvapi-...
  RAGE_LLM_MODEL     = meta/llama-3.3-70b-instruct

Judge backend (Layer 3 — smaller, faster model):
  RAGE_JUDGE_BASE_URL = https://integrate.api.nvidia.com/v1  (optional, defaults to LLM base)
  RAGE_JUDGE_API_KEY  = nvapi-...                             (optional, defaults to LLM key)
  RAGE_JUDGE_MODEL    = nvidia/llama-3.1-nemotron-nano-8b-v1
  RAGE_USE_LLM_JUDGE  = 1

Fallback: OPENAI_API_KEY for plain OpenAI usage.

The judge client can point to a different model or provider than the main
assistant — e.g. a small Nemotron Nano 8B judges while a 70B model responds.
"""
from __future__ import annotations

import os
from typing import Any

_NIM_BASE = "https://integrate.api.nvidia.com/v1"


def get_nim_env_hint() -> str:
    """Return the minimum env var block needed to use NVIDIA NIM."""
    return (
        "  export RAGE_LLM_BASE_URL=https://integrate.api.nvidia.com/v1\n"
        "  export RAGE_LLM_API_KEY=nvapi-...        (from build.nvidia.com)\n"
        "  export RAGE_LLM_MODEL=meta/llama-3.3-70b-instruct\n"
        "  export RAGE_JUDGE_MODEL=nvidia/llama-3.1-nemotron-nano-8b-v1\n"
        "  export RAGE_USE_LLM_JUDGE=1"
    )


def llm_judge_enabled() -> bool:
    """Return True when the LLM judge is explicitly enabled."""
    flag = os.environ.get("RAGE_USE_LLM_JUDGE", "").lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    # Auto-enable only when a plain OPENAI_API_KEY is set (legacy path).
    # NVIDIA NIM requires explicit opt-in to avoid unexpected API calls.
    return bool(os.environ.get("OPENAI_API_KEY"))


def get_llm_client() -> Any | None:
    """Return an OpenAI-compatible client for the main assistant, or None."""
    try:
        import openai  # type: ignore
    except ImportError:
        return None

    base = os.environ.get("RAGE_LLM_BASE_URL")
    if base:
        key = os.environ.get("RAGE_LLM_API_KEY", "")
        return openai.OpenAI(base_url=base, api_key=key)

    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return openai.OpenAI(api_key=key)

    return None


def get_judge_client() -> Any | None:
    """Return an OpenAI-compatible client for the L3 judge.

    Uses RAGE_JUDGE_BASE_URL / RAGE_JUDGE_API_KEY when set so the judge
    can be a different model (e.g. Nemotron Nano 8B) than the main assistant.
    Falls back to the main assistant client when no judge-specific config exists.
    """
    try:
        import openai  # type: ignore
    except ImportError:
        return None

    base = os.environ.get("RAGE_JUDGE_BASE_URL") or os.environ.get("RAGE_LLM_BASE_URL")
    key = os.environ.get("RAGE_JUDGE_API_KEY") or os.environ.get("RAGE_LLM_API_KEY")

    if base and key:
        return openai.OpenAI(base_url=base, api_key=key)

    return get_llm_client()


def get_llm_model(default: str = "meta/llama-3.3-70b-instruct") -> str:
    """Resolve the chat/completion model name from environment."""
    return os.environ.get("RAGE_LLM_MODEL") or default


def get_judge_model(default: str | None = None) -> str:
    """Resolve the L3 judge model (smaller/faster model recommended)."""
    return (
        os.environ.get("RAGE_JUDGE_MODEL")
        or default
        or get_llm_model()
    )


def has_llm_backend() -> bool:
    """True when any LLM backend is configured."""
    return get_llm_client() is not None
