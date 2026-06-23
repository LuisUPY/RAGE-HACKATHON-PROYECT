"""Unified LLM bootstrap for demos and interactive CLIs."""
from __future__ import annotations

import os
import sys

from rage_core.config.dual_api_setup import prompt_dual_api_setup
from rage_core.config.env_loader import (
    bootstrap_nvidia_master_key,
    ensure_env_loaded,
    prompt_session_api_keys,
)
from rage_core.llm.openai_compat import (
    diagnose_llm_setup,
    get_judge_model,
    get_llm_model,
    has_llm_backend,
    llm_judge_enabled,
    verify_llm_connection,
)


def _has_valid_key() -> bool:
    ensure_env_loaded()
    for key in ("RAGE_LLM_API_KEY", "RAGE_NVIDIA_API_KEY", "OPENAI_API_KEY"):
        val = (os.environ.get(key) or "").strip()
        if val and "PEGAR_AQUI" not in val and val not in ("nvapi-...", "sk-..."):
            return True
    return False


def ensure_llm_ready(
    *,
    interactive: bool = True,
    verify: bool = True,
    require_judge: bool = False,
    force_prompt: bool | None = None,
    dual_api: bool = False,
) -> tuple[bool, str]:
    """Configure LLM backend via interactive prompt or process environment.

    On an interactive terminal, API keys are requested each run (session-only;
    never read from .env). Pass force_prompt=False to reuse keys already in the
    environment (tests, CI). Returns (ok, message). Never raises.
    """
    ensure_env_loaded()
    if force_prompt is None:
        force_prompt = interactive and sys.stdin.isatty()

    if force_prompt and interactive and sys.stdin.isatty():
        prompt_fn = prompt_dual_api_setup if dual_api else prompt_session_api_keys
        if not prompt_fn(verify=verify):
            return False, "Se canceló: faltan API keys."
    elif _has_valid_key():
        os.environ.setdefault("RAGE_USE_LLM_JUDGE", "1")
        bootstrap_nvidia_master_key()
    elif interactive and sys.stdin.isatty():
        if not prompt_session_api_keys():
            return False, "Se canceló: faltan API keys."
    else:
        return False, diagnose_llm_setup()

    if not has_llm_backend():
        return False, diagnose_llm_setup()

    if require_judge and not llm_judge_enabled():
        return False, "El juez LLM no está activo. Define RAGE_USE_LLM_JUDGE=1 y una API key."

    if verify:
        model = get_llm_model()
        judge = get_judge_model("nvidia/llama-3.1-nemotron-nano-8b-v1") if llm_judge_enabled() else None
        ok, err = verify_llm_connection(model=model, judge_model=judge)
        if not ok:
            if interactive and sys.stdin.isatty():
                print(err, file=sys.stderr)
                print("\nVuelve a pegar la API key.\n", file=sys.stderr)
                if not prompt_session_api_keys():
                    return False, "Verificación LLM fallida."
                ok, err = verify_llm_connection(model=model, judge_model=judge)
            if not ok:
                return False, err

    return True, "LLM configurado."
