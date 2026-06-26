"""Tests for .env loading (secrets never read from disk)."""
from __future__ import annotations

import os
from pathlib import Path

from rage_core.config.env_loader import load_env_file


def test_load_env_file_skips_api_secrets(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "RAGE_NVIDIA_API_KEY=nvapi-should-not-load",
                "RAGE_LLM_API_KEY=nvapi-should-not-load",
                "OPENAI_API_KEY=sk-should-not-load",
                "RAGE_LLM_MODEL=custom/model",
                "RAGE_USE_LLM_JUDGE=0",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("RAGE_NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("RAGE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RAGE_LLM_MODEL", raising=False)
    monkeypatch.delenv("RAGE_USE_LLM_JUDGE", raising=False)

    assert load_env_file(env_file) is True
    assert os.environ.get("RAGE_NVIDIA_API_KEY") is None
    assert os.environ.get("RAGE_LLM_API_KEY") is None
    assert os.environ.get("OPENAI_API_KEY") is None
    assert os.environ.get("RAGE_LLM_MODEL") == "custom/model"
    assert os.environ.get("RAGE_USE_LLM_JUDGE") == "0"
