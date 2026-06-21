"""
Shared OpenAI-compatible client for cloud APIs and local Ollama.

Ollama exposes an OpenAI-compatible API at http://localhost:11434/v1.
Set RAGE_LLM_BASE_URL or OLLAMA_BASE_URL to use it.

NVIDIA NIM also uses the same OpenAI-compatible protocol:
  RAGE_LLM_BASE_URL=https://integrate.api.nvidia.com/v1
  RAGE_LLM_API_KEY=nvapi-...

The judge client (Layer 3) can be configured independently so a small model
(e.g. nvidia/llama-3.1-nemotron-nano-8b-v1) handles YES/NO classification
while a larger model handles the main conversation.
"""
from __future__ import annotations

import os
from typing import Any


def llm_judge_enabled() -> bool:
    """Return True when an LLM judge backend is configured."""
    flag = os.environ.get("RAGE_USE_LLM_JUDGE", "").lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    # Judge is opt-in only — avoids false positives when using small local models.
    return bool(os.environ.get("OPENAI_API_KEY"))


def get_llm_client() -> Any | None:
    """Return an OpenAI-compatible client for the main assistant, or None."""
    try:
        import openai  # type: ignore
    except ImportError:
        return None

    base = os.environ.get("RAGE_LLM_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")
    if base:
        api_key = (
            os.environ.get("RAGE_LLM_API_KEY")
            or os.environ.get("OLLAMA_API_KEY")
            or "ollama"
        )
        return openai.OpenAI(base_url=base, api_key=api_key)

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return openai.OpenAI(api_key=api_key)
    return None


def get_judge_client() -> Any | None:
    """Return an OpenAI-compatible client for the L3 judge.

    Uses RAGE_JUDGE_BASE_URL / RAGE_JUDGE_API_KEY when set, so the judge
    can point to a different model or even a different provider than the
    main assistant (e.g. a small Nemotron Nano 8B on NVIDIA NIM while the
    assistant is a 70B model on the same endpoint).

    Falls back to the main assistant client when no judge-specific config exists.
    """
    try:
        import openai  # type: ignore
    except ImportError:
        return None

    base = os.environ.get("RAGE_JUDGE_BASE_URL") or os.environ.get("RAGE_LLM_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")
    key = (
        os.environ.get("RAGE_JUDGE_API_KEY")
        or os.environ.get("RAGE_LLM_API_KEY")
        or os.environ.get("OLLAMA_API_KEY")
    )
    if base and key:
        return openai.OpenAI(base_url=base, api_key=key)

    # Last resort: fall back to the main client (covers plain OPENAI_API_KEY setups)
    return get_llm_client()


def get_llm_model(default: str = "gpt-4o-mini") -> str:
    """Resolve the chat/completion model name from environment."""
    return (
        os.environ.get("RAGE_LLM_MODEL")
        or os.environ.get("OLLAMA_MODEL")
        or default
    )


def get_judge_model(default: str | None = None) -> str:
    """Resolve the L3 judge model (smaller/faster model recommended)."""
    return (
        os.environ.get("RAGE_JUDGE_MODEL")
        or os.environ.get("OLLAMA_JUDGE_MODEL")
        or default
        or get_llm_model()
    )


def has_llm_backend() -> bool:
    """True when any LLM backend (Ollama, NVIDIA NIM, or OpenAI) is configured."""
    return get_llm_client() is not None
