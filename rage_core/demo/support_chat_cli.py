"""
Interactive IT support chat: rage-chat-support

Pide tus API keys al iniciar cada sesión (no usa .env para secretos).
"""
from __future__ import annotations

import argparse
import sys

from rage_core.config.env_loader import prompt_session_api_keys
from rage_core.demo.support_agent import LocalSupportAgent
from rage_core.llm.openai_compat import (
    diagnose_llm_setup,
    get_judge_model,
    get_llm_client,
    get_llm_model,
    has_llm_backend,
    llm_judge_enabled,
    verify_llm_connection,
)


def _print_rage_signal(signal) -> None:
    l1 = signal.layer1
    l2 = signal.layer2
    l3 = signal.layer3
    print("  --- RAGE último turno ---")
    print(f"  Score/banda : {signal.score:.1f} / {signal.band.value}")
    print(f"  L1 regex    : {'SÍ ' + l1.pattern_id if l1.matched else 'no'}")
    print(f"  L2 RAG      : {l2.score:.3f}  match={l2.top_match_id or '—'}  sev={l2.severity or '—'}")
    print(
        f"  L3 drift    : turn={l3.drift:.3f}  cumulative={l3.cumulative_drift:.3f}  "
        f"suspicious={'SÍ' if l3.suspicious else 'no'}"
    )
    print(f"  Juez LLM    : {'SÍ — ATAQUE' if l3.llm_flagged else 'no'}")


def _print_turn_result(result) -> None:
    if result.blocked:
        print(f"\n[Sistema]> {result.assistant_text}")
    else:
        print(f"\nSoporte> {result.assistant_text}")
    if result.signal.layer3.suspicious or result.signal.layer1.matched:
        _print_rage_signal(result.signal)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE IT support chat — juez LLM + defensa multi-turno",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Modelo asistente (default: RAGE_LLM_MODEL o meta/llama-3.3-70b-instruct)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Omitir prueba de conexión al iniciar (no recomendado)",
    )
    args = parser.parse_args()

    if not prompt_session_api_keys():
        return 1

    if not has_llm_backend():
        print("No se pudo configurar el backend LLM.", file=sys.stderr)
        print(diagnose_llm_setup(), file=sys.stderr)
        return 1

    client = get_llm_client()
    if client is None:
        print("Instala openai: uv sync --extra openai", file=sys.stderr)
        return 1

    model = args.model or get_llm_model()
    judge_model = get_judge_model("nvidia/llama-3.1-nemotron-nano-8b-v1")

    if not args.no_verify:
        print("\nVerificando conexión con el LLM...")
        ok, err = verify_llm_connection(
            model=model,
            judge_model=judge_model if llm_judge_enabled() else None,
        )
        if not ok:
            print(err, file=sys.stderr)
            return 1
        print("✓ Conexión OK")

    agent = LocalSupportAgent(model=model)

    print()
    print("=" * 62)
    print("  RAGE — Chat de SOPORTE TÉCNICO (IT Helpdesk CRM)")
    print("  Rol: asistente interno de tickets, informes y exports agregados")
    print(f"  Asistente : {model}")
    print(f"  Juez L3   : {judge_model}  ({'ACTIVO' if llm_judge_enabled() else 'OFF'})")
    print("  Defensa   : L1 + L2 RAG + drift + juez + contexto multi-turno")
    print("-" * 62)
    print("  Comandos: /quit  /status  /rage  /reset")
    print("  Prueba mensajes del dataset practice o tus propios escenarios.")
    print("=" * 62)

    while True:
        try:
            user_text = input("\nUsuario> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSesión terminada.")
            return 0

        if not user_text:
            continue
        low = user_text.lower()
        if low in ("/quit", "/exit", "/q"):
            print("Sesión terminada.")
            return 0
        if low == "/status":
            print(
                f"  turnos={agent.state.turn_index}  "
                f"session_risk={agent.state.session_risk_score:.3f}  "
                f"juez={'ON' if llm_judge_enabled() else 'OFF'}  "
                f"prior_l2_peak={agent._prior_l2_peak:.2f}  "
                f"prior_drift_peak={agent._prior_drift_peak:.2f}"
            )
            continue
        if low == "/rage":
            if agent.last_signal is None:
                print("  (aún no hay turnos evaluados)")
            else:
                _print_rage_signal(agent.last_signal)
            continue
        if low == "/reset":
            agent = LocalSupportAgent(model=model)
            print("  Conversación reiniciada — estado RAGE limpio.")
            continue

        result = agent.handle_turn(user_text)
        _print_turn_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
