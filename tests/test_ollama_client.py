"""Tests for the OpenAI-compatible LLM client helpers (NVIDIA NIM backend)."""
from __future__ import annotations

import pytest

from rage_core.llm.openai_compat import (
    diagnose_llm_setup,
    get_judge_client,
    get_judge_model,
    get_llm_client,
    get_llm_model,
    has_llm_backend,
    llm_judge_enabled,
)


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all RAGE LLM env vars before each test."""
    for key in (
        "OPENAI_API_KEY",
        "RAGE_LLM_BASE_URL",
        "RAGE_LLM_API_KEY",
        "RAGE_LLM_MODEL",
        "RAGE_JUDGE_BASE_URL",
        "RAGE_JUDGE_API_KEY",
        "RAGE_JUDGE_MODEL",
        "RAGE_USE_LLM_JUDGE",
    ):
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------- #
# llm_judge_enabled                                                            #
# --------------------------------------------------------------------------- #

def test_llm_judge_disabled_without_config() -> None:
    assert llm_judge_enabled() is False


def test_llm_judge_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGE_USE_LLM_JUDGE", "1")
    assert llm_judge_enabled() is True


def test_llm_judge_disabled_with_zero_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGE_USE_LLM_JUDGE", "0")
    assert llm_judge_enabled() is False


def test_llm_judge_auto_enabled_with_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENAI_API_KEY alone auto-enables judge (legacy path)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert llm_judge_enabled() is True


# --------------------------------------------------------------------------- #
# get_llm_model / get_judge_model                                              #
# --------------------------------------------------------------------------- #

def test_get_llm_model_default() -> None:
    assert get_llm_model() == "meta/llama-3.3-70b-instruct"


def test_get_llm_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGE_LLM_MODEL", "meta/llama-3.1-70b-instruct")
    assert get_llm_model() == "meta/llama-3.1-70b-instruct"


def test_get_judge_model_default() -> None:
    """Without config, judge model falls back to main model default."""
    assert get_judge_model() == "meta/llama-3.3-70b-instruct"


def test_get_judge_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGE_JUDGE_MODEL", "nvidia/llama-3.1-nemotron-nano-8b-v1")
    assert get_judge_model() == "nvidia/llama-3.1-nemotron-nano-8b-v1"


def test_get_judge_model_independent_from_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGE_LLM_MODEL", "meta/llama-3.3-70b-instruct")
    monkeypatch.setenv("RAGE_JUDGE_MODEL", "nvidia/llama-3.1-nemotron-nano-8b-v1")
    assert get_llm_model() == "meta/llama-3.3-70b-instruct"
    assert get_judge_model() == "nvidia/llama-3.1-nemotron-nano-8b-v1"


# --------------------------------------------------------------------------- #
# get_llm_client                                                               #
# --------------------------------------------------------------------------- #

def test_has_llm_backend_false_without_config() -> None:
    assert has_llm_backend() is False


def test_get_llm_client_nim(monkeypatch: pytest.MonkeyPatch) -> None:
    openai = pytest.importorskip("openai")
    monkeypatch.setenv("RAGE_LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("RAGE_LLM_API_KEY", "nvapi-test")
    client = get_llm_client()
    assert client is not None
    assert isinstance(client, openai.OpenAI)
    assert "nvidia.com" in str(client.base_url)


def test_get_llm_client_openai_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    openai = pytest.importorskip("openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = get_llm_client()
    assert client is not None
    assert isinstance(client, openai.OpenAI)


def test_get_llm_client_none_without_config() -> None:
    assert get_llm_client() is None


def test_get_llm_client_none_with_base_but_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("openai")
    monkeypatch.setenv("RAGE_LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    assert get_llm_client() is None
    assert has_llm_backend() is False


def test_diagnose_llm_setup_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("openai")
    monkeypatch.setenv("RAGE_LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    msg = diagnose_llm_setup()
    assert "RAGE_LLM_API_KEY" in msg


def test_diagnose_llm_setup_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("openai")
    msg = diagnose_llm_setup()
    assert "API key" in msg


# --------------------------------------------------------------------------- #
# get_judge_client                                                              #
# --------------------------------------------------------------------------- #

def test_get_judge_client_uses_judge_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """RAGE_JUDGE_BASE_URL + RAGE_JUDGE_API_KEY produce un cliente independiente."""
    openai = pytest.importorskip("openai")
    monkeypatch.setenv("RAGE_JUDGE_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("RAGE_JUDGE_API_KEY", "nvapi-judge")
    client = get_judge_client()
    assert client is not None
    assert isinstance(client, openai.OpenAI)
    assert "nvidia.com" in str(client.base_url)


def test_get_judge_client_falls_back_to_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin RAGE_JUDGE_BASE_URL, el juez usa el mismo cliente que el asistente."""
    openai = pytest.importorskip("openai")
    monkeypatch.setenv("RAGE_LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("RAGE_LLM_API_KEY", "nvapi-main")
    client = get_judge_client()
    assert client is not None
    assert isinstance(client, openai.OpenAI)


def test_get_judge_client_none_without_config() -> None:
    assert get_judge_client() is None


def test_get_judge_client_full_nim_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Perfil NVIDIA NIM completo: asistente y juez en el mismo endpoint."""
    openai = pytest.importorskip("openai")
    nim = "https://integrate.api.nvidia.com/v1"
    monkeypatch.setenv("RAGE_LLM_BASE_URL", nim)
    monkeypatch.setenv("RAGE_LLM_API_KEY", "nvapi-main")
    monkeypatch.setenv("RAGE_LLM_MODEL", "meta/llama-3.3-70b-instruct")
    monkeypatch.setenv("RAGE_JUDGE_BASE_URL", nim)
    monkeypatch.setenv("RAGE_JUDGE_API_KEY", "nvapi-judge")
    monkeypatch.setenv("RAGE_JUDGE_MODEL", "nvidia/llama-3.1-nemotron-nano-8b-v1")
    monkeypatch.setenv("RAGE_USE_LLM_JUDGE", "1")

    assert llm_judge_enabled() is True
    assert get_llm_model() == "meta/llama-3.3-70b-instruct"
    assert get_judge_model() == "nvidia/llama-3.1-nemotron-nano-8b-v1"

    main_client = get_llm_client()
    judge_client = get_judge_client()
    assert main_client is not None
    assert judge_client is not None
    assert isinstance(main_client, openai.OpenAI)
    assert isinstance(judge_client, openai.OpenAI)
