"""Track A product demo — dual API wizard + RAGE gate + per-turn latency."""
from __future__ import annotations

import argparse
import sys

from rage_core.chat.profile_chatbot import ProfileChatResult, ProfileChatbot
from rage_core.demo.bootstrap import ensure_llm_ready
from rage_core.gate.chat_gate import GateResult
from rage_core.llm.openai_compat import get_judge_model, get_llm_model, llm_judge_enabled
from rage_core.profiles.bot_profile import list_profiles, load_bot_profile


def _short_name(profile) -> str:
    return profile.display_name.split("—")[0].strip()


def _format_latency(turn: ProfileChatResult) -> str:
    judge_part = f"judge {turn.judge_ms:.0f}ms" if turn.gate.judge_used else "judge skipped"
    assistant_part = (
        f"assistant {turn.assistant_ms:.0f}ms"
        if turn.assistant_ms > 0
        else ("assistant —" if turn.gate.blocked else "assistant mock")
    )
    return (
        f"  [RAGE] {turn.gate.action}  |  RAGE {turn.rage_ms:.0f}ms  |  "
        f"{judge_part}  |  {assistant_part}  |  total {turn.total_ms:.0f}ms"
    )


def _print_gate_panel(gate: GateResult) -> None:
    s = gate.signal
    label = "RAGE+Juez" if gate.judge_used else "RAGE"
    print(f"  [{label}] {gate.action.upper()} — {gate.judge_reason}")
    print(
        f"  L1: {s.layer1.pattern_id or '—'}  "
        f"L2: {s.layer2.score:.2f}  "
        f"drift: {s.layer3.drift:.2f}  "
        f"cumulative: {s.layer3.cumulative_drift:.2f}"
    )
    print(f"  Briefing: {gate.briefing.to_text().replace(chr(10), ' | ')}")


def _print_last(turn: ProfileChatResult | None) -> None:
    if turn is None:
        print("  (sin turnos aún)")
        return
    gate = turn.gate
    print("  --- Último turno — RAGE briefing + juez ---")
    print(f"  Usuario   : {turn.user_text[:120]}")
    print(f"  Acción    : {gate.action.upper()}  (juez={'SÍ' if gate.judge_used else 'no'})")
    print(f"  Motivo    : {gate.judge_reason}")
    print(gate.briefing.to_text().replace("\n", "\n  "))
    if turn.gate.blocked:
        print(f"  Respuesta : {turn.assistant_text[:200]}")
    print(_format_latency(turn))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE product demo — dual API, perfiles ricos, latencia por turno",
    )
    parser.add_argument(
        "--profile",
        default="restaurant",
        choices=list_profiles(),
        help="Perfil de empresa",
    )
    parser.add_argument("--list-profiles", action="store_true", help="Listar perfiles")
    parser.add_argument("--offline", action="store_true", help="Sin API — juez por reglas + respuestas mock")
    parser.add_argument("--model", default=None, help="Modelo asistente (override)")
    args = parser.parse_args()

    if args.list_profiles:
        print("Perfiles disponibles:")
        for pid in list_profiles():
            p = load_bot_profile(pid)
            print(f"  {pid:<12} {p.display_name}")
        return 0

    profile = load_bot_profile(args.profile)

    if not args.offline:
        ok, err = ensure_llm_ready(
            interactive=True,
            verify=True,
            require_judge=True,
            force_prompt=True,
            dual_api=True,
        )
        if not ok:
            print(err, file=sys.stderr)
            return 1

    model = args.model or get_llm_model()
    bot = ProfileChatbot(profile=profile, model=model)
    show_latency = True
    verbose_rage = False
    last_turn: ProfileChatResult | None = None

    print()
    print("=" * 62)
    print(f"  RAGE Product Demo — {profile.display_name}")
    print(f"  Rol      : {profile.role}")
    print(f"  Propósito: {profile.purpose[:70]}...")
    if args.offline:
        print("  Modo     : OFFLINE")
    else:
        print(f"  Asistente: {model}")
        print(f"  Juez     : {get_judge_model()} ({'ON' if llm_judge_enabled() else 'OFF'})")
    print("  Flujo    : RAGE detecta → Juez (si hay riesgo) → asistente")
    print("-" * 62)
    print("  /quit  /reset  /profile  /models  /last  /latency  /verbose")
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
            return 0
        if low == "/reset":
            bot.reset()
            last_turn = None
            print("  Estado reiniciado.")
            continue
        if low == "/profile":
            print(profile.judge_context_block())
            continue
        if low == "/models":
            if args.offline:
                print("  Modo offline — sin modelos LLM.")
            else:
                print(f"  Asistente: {model}")
                print(f"  Juez     : {get_judge_model()}")
            continue
        if low == "/last":
            _print_last(last_turn)
            continue
        if low == "/latency":
            show_latency = not show_latency
            print(f"  Latencia por turno: {'ON' if show_latency else 'OFF'}")
            continue
        if low == "/verbose":
            verbose_rage = not verbose_rage
            print(f"  Panel RAGE siempre: {'ON' if verbose_rage else 'OFF'}")
            continue

        turn = bot.handle_turn(user_text, offline=args.offline)
        last_turn = turn

        if turn.gate.blocked:
            print(f"\n[Sistema]> {turn.assistant_text}")
        else:
            print(f"\n{_short_name(profile)}> {turn.assistant_text}")

        flagged = (
            turn.gate.judge_used
            or turn.gate.briefing.policy_would_block
            or turn.gate.signal.layer3.suspicious
            or turn.gate.blocked
        )
        if verbose_rage or flagged:
            _print_gate_panel(turn.gate)
        if show_latency:
            print(_format_latency(turn))


if __name__ == "__main__":
    raise SystemExit(main())
