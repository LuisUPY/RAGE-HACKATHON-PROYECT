"""Tests for ollama mode in CrescendoAttackLLM."""
from rage_core.redteam.attack_llm import CrescendoAttackLLM


def test_supported_models_includes_ollama() -> None:
    assert "ollama" in CrescendoAttackLLM.SUPPORTED_MODELS


def test_use_llm_false_for_offline() -> None:
    attacker = CrescendoAttackLLM(model="offline")
    assert attacker._use_llm() is False


def test_resolve_model_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    attacker = CrescendoAttackLLM(model="ollama")
    assert attacker._resolve_model() == "qwen2.5:7b-instruct"
