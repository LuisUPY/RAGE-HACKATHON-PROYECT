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
import re
from typing import Any

_NIM_BASE = "https://integrate.api.nvidia.com/v1"
_INVISIBLE_CHARS_RE = re.compile(r"[\r\n\t\u200b\uFEFF\u00a0]")


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


def sanitize_api_key(value: str | None) -> str:
    """Normalize pasted API keys (quotes, line breaks, Bearer prefix, invisible chars)."""
    if not value:
        return ""
    key = value.strip()
    key = _INVISIBLE_CHARS_RE.sub("", key)
    key = key.strip().strip('"').strip("'")
    if key.lower().startswith("bearer "):
        key = key[7:].strip().strip('"').strip("'")
    return key


def _clean_key(value: str | None) -> str:
    return sanitize_api_key(value)


def get_llm_client() -> Any | None:
    """Return an OpenAI-compatible client for the main assistant, or None."""
    try:
        import openai  # type: ignore
    except ImportError:
        return None

    base = os.environ.get("RAGE_LLM_BASE_URL", "").strip()
    if base:
        key = _clean_key(os.environ.get("RAGE_LLM_API_KEY"))
        if not key:
            return None
        return openai.OpenAI(base_url=base, api_key=key)

    key = _clean_key(os.environ.get("OPENAI_API_KEY"))
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
    key = _clean_key(os.environ.get("RAGE_JUDGE_API_KEY") or os.environ.get("RAGE_LLM_API_KEY"))

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


def diagnose_llm_setup() -> str:
    """Return a user-facing hint explaining why the LLM backend is unavailable."""
    try:
        import openai  # noqa: F401
    except ImportError:
        return (
            "Falta el paquete openai.\n"
            "  Ejecuta: uv sync\n"
            "  (o: uv sync --extra openai)"
        )

    llm_key = _clean_key(os.environ.get("RAGE_LLM_API_KEY"))
    openai_key = _clean_key(os.environ.get("OPENAI_API_KEY"))
    base = os.environ.get("RAGE_LLM_BASE_URL", "").strip()

    if base and llm_key and not llm_key.startswith("nvapi-"):
        return (
            "La clave NVIDIA no tiene formato nvapi-...\n"
            "  Debe generarse en https://build.nvidia.com (no en ngc.nvidia.com)."
        )
    if base and not llm_key:
        return (
            "Hay RAGE_LLM_BASE_URL pero falta RAGE_LLM_API_KEY.\n"
            "  Vuelve a pegar tu clave NVIDIA (nvapi-...) al iniciar el chat."
        )
    if not llm_key and not openai_key:
        return (
            "No hay API key configurada en esta sesión.\n"
            "  NVIDIA: https://build.nvidia.com → API Keys\n"
            "  O usa una clave OpenAI (sk-...)."
        )
    return "Configuración LLM incompleta — revisa las variables de entorno."


def format_llm_api_error(exc: Exception, *, model: str | None = None) -> str:
    """Translate common LLM HTTP errors into actionable Spanish hints."""
    text = str(exc).lower()
    model_hint = f"\n  Modelo usado: {model}" if model else ""

    if any(token in text for token in ("401", "unauthorized", "authentication failed")):
        return (
            f"Error 401 — NVIDIA rechazó la autenticación.{model_hint}\n\n"
            "Comprueba:\n"
            "  1. Clave de https://build.nvidia.com (NO de ngc.nvidia.com)\n"
            "  2. Generarla en la página del modelo → «Get API Key»\n"
            "  3. Debe empezar por nvapi- (sin espacios ni comillas al pegar)\n"
            "  4. Aceptar los términos del modelo en build.nvidia.com\n"
            "  5. Rotar la clave en build.nvidia.com/settings/api-keys si es antigua\n\n"
            f"Detalle técnico: {exc}"
        )

    if "403" in text or "forbidden" in text:
        return (
            f"Error 403 — la clave no tiene permiso «Public API Endpoints».{model_hint}\n\n"
            "Crea una clave nueva en https://build.nvidia.com:\n"
            "  • Entra a un modelo (ej. Llama 3.1 8B)\n"
            "  • Pulsa «Get API Key» y acepta términos\n"
            "  • No uses claves del portal NGC\n\n"
            f"Detalle técnico: {exc}"
        )

    if "404" in text and model:
        return (
            f"Modelo no disponible: {model}\n"
            "  Prueba: uv run rage-chat-support --model meta/llama-3.1-8b-instruct\n"
            f"Detalle técnico: {exc}"
        )

    return f"[ERROR] LLM request failed: {exc}"


def verify_llm_connection(
    *,
    model: str | None = None,
    judge_model: str | None = None,
) -> tuple[bool, str]:
    """Ping assistant (and optional judge) before starting interactive chat."""
    model = model or get_llm_model()
    client = get_llm_client()
    if client is None:
        return False, diagnose_llm_setup()

    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001
        return False, format_llm_api_error(exc, model=model)

    if judge_model and llm_judge_enabled():
        judge_client = get_judge_client()
        if judge_client is None:
            return False, "Juez LLM activo pero no hay cliente configurado."
        try:
            judge_client.chat.completions.create(
                model=judge_model,
                messages=[{"role": "user", "content": "Reply NO"}],
                max_tokens=1,
                temperature=0,
            )
        except Exception as exc:  # noqa: BLE001
            return False, (
                "El asistente respondió, pero el juez LLM falló:\n"
                + format_llm_api_error(exc, model=judge_model)
            )

    return True, ""
