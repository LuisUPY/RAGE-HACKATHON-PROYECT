"""Interactive company chatbot — configurable profile + RAGE + session judge."""
from __future__ import annotations

import argparse
import sys

from rage_core.chat.profile_chatbot import ProfileChatbot
from rage_core.demo.bootstrap import ensure_llm_ready
from rage_core.llm.openai_compat import get_judge_model, get_llm_model, llm_judge_enabled
from rage_core.profiles.bot_profile import list_profiles, load_bot_profile


def _print_gate(gate) -> None:
    s = gate.signal
    print("  --- RAGE + Juez de sesión ---")
    print(f"  Acción    : {gate.action.upper()}  (juez={'SÍ' if gate.judge_used else 'no'})")
    print(f"  Motivo    : {gate.judge_reason}")
    print(f"  Score     : {s.score:.1f} / {s.band.value}")
    print(f"  L1        : {s.layer1.pattern_id or '—'}")
    print(f"  L2        : {s.layer2.score:.3f}")
    print(
        f"  L3 drift  : {s.layer3.drift:.3f}  cumulative={s.layer3.cumulative_drift:.3f}  "
        f"suspicious={'SÍ' if s.layer3.suspicious else 'no'}"
    )
    print(f"  Briefing  : policy would {'BLOCK' if gate.briefing.policy_would_block else 'ALLOW'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE company chatbot — perfil adaptable + juez contextual multi-turno",
    )
    parser.add_argument(
        "--profile",
        default="restaurant",
        choices=list_profiles(),
        help="Perfil de empresa (rol, propósito, políticas)",
    )
    parser.add_argument("--list-profiles", action="store_true", help="Listar perfiles")
    parser.add_argument("--offline", action="store_true", help="Sin API — juez por reglas + respuestas mock")
    parser.add_argument("--model", default=None, help="Modelo asistente LLM")
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
        )
        if not ok:
            print(err, file=sys.stderr)
            return 1

    model = args.model or get_llm_model()
    bot = ProfileChatbot(profile=profile, model=model)

    print()
    print("=" * 62)
    print(f"  RAGE Chatbot — {profile.display_name}")
    print(f"  Rol      : {profile.role}")
    print(f"  Propósito: {profile.purpose[:70]}...")
    if args.offline:
        print("  Modo     : OFFLINE (juez por reglas, sin LLM asistente)")
    else:
        print(f"  Asistente: {model}")
        print(f"  Juez     : {get_judge_model()} ({'ON' if llm_judge_enabled() else 'OFF'})")
    print("  Flujo    : RAGE detecta → Juez revisa (historial + señales) → ALLOW/BLOCK/DENY")
    print("-" * 62)
    print("  Comandos: /quit  /status  /rage  /reset  /profile")
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
            print("  Estado reiniciado.")
            continue
        if low == "/profile":
            print(profile.judge_context_block())
            continue
        if low == "/status":
            st = bot.gate.state
            print(
                f"  turnos={st.turn_index}  risk={st.session_risk_score:.3f}  "
                f"prior_l2={bot.gate._prior_l2_peak:.2f}  "  # noqa: SLF001
                f"prior_drift={bot.gate._prior_drift_peak:.2f}"
            )
            continue
        if low == "/rage":
            print("  Tras cada turno revisado verás el bloque 'RAGE + Juez de sesión'.")
            continue

        turn = bot.handle_turn(user_text, offline=args.offline)
        if turn.gate.blocked:
            print(f"\n[Sistema]> {turn.assistant_text}")
        else:
            print(f"\n{profile.display_name.split('—')[0].strip()}> {turn.assistant_text}")

        if turn.gate.judge_used or turn.gate.briefing.policy_would_block or turn.gate.signal.layer3.suspicious:
            _print_gate(turn.gate)


if __name__ == "__main__":
    raise SystemExit(main())
