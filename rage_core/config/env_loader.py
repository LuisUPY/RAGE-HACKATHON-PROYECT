"""Load .env from repo root and expand RAGE_NVIDIA_API_KEY into LLM/judge vars."""
from __future__ import annotations

import os
from pathlib import Path

_PLACEHOLDER_MARKERS = ("PEGAR_AQUI", "nvapi-...", "sk-...")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    return any(m in v for m in _PLACEHOLDER_MARKERS)


def load_env_file(path: Path | None = None) -> bool:
    """Parse a simple KEY=VALUE .env file into os.environ. Returns True if loaded."""
    env_path = path or (_REPO_ROOT / ".env")
    if not env_path.is_file():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value
    return True


def bootstrap_nvidia_master_key() -> None:
    """Copy RAGE_NVIDIA_API_KEY into RAGE_LLM_API_KEY and RAGE_JUDGE_API_KEY if set."""
    master = os.environ.get("RAGE_NVIDIA_API_KEY", "").strip()
    if _is_placeholder(master):
        return
    os.environ["RAGE_LLM_API_KEY"] = master
    os.environ["RAGE_JUDGE_API_KEY"] = master
    os.environ.setdefault("RAGE_LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    os.environ.setdefault("RAGE_JUDGE_BASE_URL", "https://integrate.api.nvidia.com/v1")
    os.environ.setdefault("RAGE_USE_LLM_JUDGE", "1")


def prompt_session_api_keys() -> bool:
    """Ask for API keys interactively each session (not saved to disk). Returns True if configured."""
    # Clear any keys from a previous session or .env so we always prompt fresh.
    for key in (
        "RAGE_NVIDIA_API_KEY",
        "RAGE_LLM_API_KEY",
        "RAGE_JUDGE_API_KEY",
        "OPENAI_API_KEY",
    ):
        os.environ.pop(key, None)

    print()
    print("=" * 62)
    print("  API keys — solo esta sesión (no se guardan en disco)")
    print("  Obtén clave NVIDIA: https://build.nvidia.com → API Keys")
    print("=" * 62)

    nv_key = input("\nNVIDIA API key (nvapi-...): ").strip()
    if nv_key:
        os.environ["RAGE_NVIDIA_API_KEY"] = nv_key
        bootstrap_nvidia_master_key()
        judge_key = input("Juez API key (Enter = misma clave): ").strip()
        if judge_key:
            os.environ["RAGE_JUDGE_API_KEY"] = judge_key
        os.environ["RAGE_USE_LLM_JUDGE"] = "1"
        return True

    print("\n¿Usar OpenAI en su lugar?")
    oa_key = input("OpenAI API key (sk-... o Enter para cancelar): ").strip()
    if oa_key:
        os.environ["OPENAI_API_KEY"] = oa_key
        os.environ["RAGE_USE_LLM_JUDGE"] = "1"
        return True

    print("\nSe necesita al menos una API key para continuar.")
    return False


def ensure_env_loaded() -> None:
    """Load .env from repo root and apply NVIDIA master-key bootstrap."""
    load_env_file()
    bootstrap_nvidia_master_key()


def env_configured() -> tuple[bool, str]:
    """Return (ok, message) for user-facing setup hints."""
    ensure_env_loaded()
    llm_key = os.environ.get("RAGE_LLM_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not _is_placeholder(llm_key):
        return True, "NVIDIA NIM configurado (RAGE_NVIDIA_API_KEY / RAGE_LLM_API_KEY)"
    if not _is_placeholder(openai_key):
        return True, "OpenAI configurado (OPENAI_API_KEY)"
    return False, (
        "Falta la API key.\n"
        "  1. ./scripts/setup-env.sh\n"
        "  2. Edita .env y pega tu clave en RAGE_NVIDIA_API_KEY=...\n"
        "  3. ./scripts/run-support-chat.sh"
    )
