"""Tests for Ollama / OpenAI-compatible LLM client helpers."""
from __future__ import annotations

import pytest

from rage_core.llm.openai_compat import (
    get_judge_model,
    get_llm_client,
    get_llm_model,
    has_llm_backend,
    llm_judge_enabled,
)


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "OPENAI_API_KEY",
        "OLLAMA_BASE_URL",
        "OLLAMA_API_KEY",
        "OLLAMA_MODEL",
        "OLLAMA_JUDGE_MODEL",
        "RAGE_LLM_BASE_URL",
        "RAGE_LLM_API_KEY",
        "RAGE_LLM_MODEL",
        "RAGE_JUDGE_MODEL",
        "RAGE_USE_LLM_JUDGE",
    ):
        monkeypatch.delenv(key, raising=False)


def test_llm_judge_disabled_without_config() -> None:
    assert llm_judge_enabled() is False


def test_llm_judge_not_auto_enabled_with_ollama_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    assert llm_judge_enabled() is False


def test_llm_judge_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGE_USE_LLM_JUDGE", "1")
    assert llm_judge_enabled() is True


def test_get_llm_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    assert get_llm_model() == "qwen2.5:7b-instruct"


def test_get_judge_model_prefers_judge_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    monkeypatch.setenv("OLLAMA_JUDGE_MODEL", "qwen2.5:3b-instruct")
    assert get_judge_model() == "qwen2.5:3b-instruct"


def test_has_llm_backend_false_without_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    assert has_llm_backend() is False


def test_get_llm_client_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    openai = pytest.importorskip("openai")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    client = get_llm_client()
    assert client is not None
    assert isinstance(client, openai.OpenAI)
