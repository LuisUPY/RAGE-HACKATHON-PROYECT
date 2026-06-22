"""Dual-model API setup — separate assistant + judge configuration."""
from __future__ import annotations

import os
import sys

from rage_core.config.env_loader import _is_placeholder, bootstrap_nvidia_master_key
from rage_core.llm.openai_compat import (
    get_judge_model,
    get_llm_model,
    llm_judge_enabled,
    sanitize_api_key,
    verify_llm_connection,
)

_NIM_BASE = "https://integrate.api.nvidia.com/v1"
_NIM_ASSISTANT_DEFAULT = "meta/llama-3.3-70b-instruct"
_NIM_JUDGE_DEFAULT = "nvidia/llama-3.1-nemotron-nano-8b-v1"
_OPENAI_DEFAULT = "gpt-4o-mini"

_SESSION_KEYS = (
    "RAGE_NVIDIA_API_KEY",
    "RAGE_LLM_API_KEY",
    "RAGE_JUDGE_API_KEY",
    "OPENAI_API_KEY",
    "RAGE_LLM_BASE_URL",
    "RAGE_JUDGE_BASE_URL",
    "RAGE_LLM_MODEL",
    "RAGE_JUDGE_MODEL",
)


def _clear_session_keys() -> None:
    for key in _SESSION_KEYS:
        os.environ.pop(key, None)


def _prompt_default(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def _validate_nvidia_key(key: str) -> str | None:
    if _is_placeholder(key):
        return "Esa clave parece un placeholder — pega tu clave real nvapi-..."
    if not key.startswith("nvapi-"):
        return "La clave NVIDIA debe empezar por nvapi- (desde build.nvidia.com)."
    return None


def _validate_openai_key(key: str) -> str | None:
    if _is_placeholder(key):
        return "Esa clave parece un placeholder — pega tu clave real sk-..."
    return None


def _configure_nvidia_block(*, label: str, default_model: str) -> tuple[str, str, str] | None:
    print(f"\n--- {label} (NVIDIA NIM) ---")
    key = sanitize_api_key(input("API key (nvapi-...): "))
    if not key:
        return None
    err = _validate_nvidia_key(key)
    if err:
        print(f"\n{err}")
        return None
    base = _prompt_default("Base URL", _NIM_BASE)
    model = _prompt_default("Model", default_model)
    return base, key, model


def _configure_openai_block(*, label: str, default_model: str) -> tuple[str, str, str] | None:
    print(f"\n--- {label} (OpenAI) ---")
    key = sanitize_api_key(input("API key (sk-...): "))
    if not key:
        return None
    err = _validate_openai_key(key)
    if err:
        print(f"\n{err}")
        return None
    base = _prompt_default("Base URL", "https://api.openai.com/v1")
    model = _prompt_default("Model", default_model)
    return base, key, model


def _apply_assistant_config(base: str, key: str, model: str) -> None:
    os.environ["RAGE_LLM_BASE_URL"] = base
    os.environ["RAGE_LLM_API_KEY"] = key
    os.environ["RAGE_LLM_MODEL"] = model
    if key.startswith("nvapi-"):
        os.environ["RAGE_NVIDIA_API_KEY"] = key


def _apply_judge_config(base: str, key: str, model: str) -> None:
    os.environ["RAGE_JUDGE_BASE_URL"] = base
    os.environ["RAGE_JUDGE_API_KEY"] = key
    os.environ["RAGE_JUDGE_MODEL"] = model


def _print_summary() -> None:
    assistant = get_llm_model()
    judge = get_judge_model()
    judge_on = "ON" if llm_judge_enabled() else "OFF"
    print()
    print("=" * 62)
    print("  Configuración dual-modelo (claves no mostradas)")
    print("=" * 62)
    print(f"  Asistente : {assistant}")
    print(f"  Juez      : {judge}  ({judge_on})")
    print("=" * 62)


def prompt_dual_api_setup(*, verify: bool = True) -> bool:
    """Interactive wizard for assistant + judge APIs. Returns True if configured."""
    _clear_session_keys()

    print()
    print("=" * 62)
    print("  Product demo — configuración dual API (solo esta sesión)")
    print("  Asistente: conversación  |  Juez: seguridad (ALLOW/BLOCK/DENY)")
    print("=" * 62)
    print()
    print("Proveedor:")
    print("  1) NVIDIA NIM — ambos modelos en NVIDIA")
    print("  2) OpenAI — ambos modelos en OpenAI")
    print("  3) Mixto — asistente y juez en proveedores distintos")
    choice = input("\nElige [1/2/3] (Enter = 1): ").strip() or "1"

    if choice == "1":
        block = _configure_nvidia_block(label="Asistente", default_model=_NIM_ASSISTANT_DEFAULT)
        if not block:
            print("\nSe necesita la API key del asistente.")
            return False
        a_base, a_key, a_model = block
        _apply_assistant_config(a_base, a_key, a_model)

        print("\n--- Juez (NVIDIA NIM) ---")
        same = input("¿Misma clave NVIDIA? [Y/n]: ").strip().lower()
        if same in ("", "y", "yes", "s", "si", "sí"):
            j_key = a_key
            j_base = a_base
        else:
            j_block = _configure_nvidia_block(label="Juez", default_model=_NIM_JUDGE_DEFAULT)
            if not j_block:
                print("\nSe necesita la API key del juez.")
                return False
            j_base, j_key, _ = j_block
        j_model = _prompt_default("Modelo juez", _NIM_JUDGE_DEFAULT)
        _apply_judge_config(j_base, j_key, j_model)

    elif choice == "2":
        block = _configure_openai_block(label="Asistente", default_model=_OPENAI_DEFAULT)
        if not block:
            print("\nSe necesita la API key del asistente.")
            return False
        a_base, a_key, a_model = block
        _apply_assistant_config(a_base, a_key, a_model)
        os.environ["OPENAI_API_KEY"] = a_key

        print("\n--- Juez (OpenAI) ---")
        same = input("¿Misma clave OpenAI? [Y/n]: ").strip().lower()
        if same in ("", "y", "yes", "s", "si", "sí"):
            j_base, j_key = a_base, a_key
        else:
            j_block = _configure_openai_block(label="Juez", default_model=_OPENAI_DEFAULT)
            if not j_block:
                print("\nSe necesita la API key del juez.")
                return False
            j_base, j_key, _ = j_block
        j_model = _prompt_default("Modelo juez", _OPENAI_DEFAULT)
        _apply_judge_config(j_base, j_key, j_model)

    elif choice == "3":
        print("\nAsistente:")
        print("  a) NVIDIA NIM")
        print("  b) OpenAI")
        a_choice = input("Elige [a/b]: ").strip().lower()
        if a_choice == "b":
            block = _configure_openai_block(label="Asistente", default_model=_OPENAI_DEFAULT)
            if block:
                a_base, a_key, a_model = block
                _apply_assistant_config(a_base, a_key, a_model)
                os.environ["OPENAI_API_KEY"] = a_key
            else:
                return False
        else:
            block = _configure_nvidia_block(label="Asistente", default_model=_NIM_ASSISTANT_DEFAULT)
            if not block:
                return False
            a_base, a_key, a_model = block
            _apply_assistant_config(a_base, a_key, a_model)

        print("\nJuez:")
        print("  a) NVIDIA NIM")
        print("  b) OpenAI")
        j_choice = input("Elige [a/b]: ").strip().lower()
        if j_choice == "b":
            block = _configure_openai_block(label="Juez", default_model=_OPENAI_DEFAULT)
            if not block:
                return False
            j_base, j_key, j_model = block
        else:
            block = _configure_nvidia_block(label="Juez", default_model=_NIM_JUDGE_DEFAULT)
            if not block:
                return False
            j_base, j_key, j_model = block
        _apply_judge_config(j_base, j_key, j_model)

    else:
        print("\nOpción no válida.")
        return False

    os.environ["RAGE_USE_LLM_JUDGE"] = "1"
    bootstrap_nvidia_master_key(force=True)
    _print_summary()

    if verify:
        ok, err = verify_llm_connection(
            model=get_llm_model(),
            judge_model=get_judge_model(),
        )
        if not ok:
            print(err, file=sys.stderr)
            return False
        print("\n✓ Asistente y juez verificados.\n")

    return True
