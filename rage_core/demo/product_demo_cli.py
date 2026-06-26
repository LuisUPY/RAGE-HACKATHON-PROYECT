"""Track A product demo — RAGE v2 UserGate + per-turn latency."""
from __future__ import annotations

import argparse
import sys

from rage_core.chat.profile_chatbot import ProfileChatResult, ProfileChatbot
from rage_core.demo.bootstrap import ensure_llm_ready
from rage_core.llm.openai_compat import get_llm_model
from rage_core.profiles.bot_profile import list_profiles, load_bot_profile
from rage_core.v2.enforce.user_gate import UserGateResult


def _short_name(profile) -> str:
  return profile.display_name.split("—")[0].strip()


def _format_latency(turn: ProfileChatResult) -> str:
  esc = (
    f"escalation {turn.escalation_ms:.0f}ms"
    if turn.gate.escalation_used
    else "escalation skipped"
  )
  assistant_part = (
    f"assistant {turn.assistant_ms:.0f}ms"
    if turn.assistant_ms > 0
    else ("assistant —" if turn.gate.blocked else "assistant mock")
  )
  return (
    f"  [RAGE v2] {turn.gate.verdict.value}  |  RAGE {turn.rage_ms:.0f}ms  |  "
    f"{esc}  |  {assistant_part}  |  total {turn.total_ms:.0f}ms"
  )


def _print_gate_panel(gate: UserGateResult) -> None:
  s = gate.signals
  print(f"  [RAGE v2] {gate.action.upper()} — score {gate.score:.0f} — {gate.verdict.value}")
  print(
    f"  L0: {s.l0.rule_id or s.l0.medium_rule_id or '—'}  "
    f"L1 domain: {s.l1.domain_score:.2f}  "
    f"trajectory: {s.l2.trajectory_score:.2f}  "
    f"hint: {s.l3.hint_score:.2f}"
  )
  if gate.reasons:
    print(f"  Reasons: {', '.join(gate.reasons)}")
  if gate.escalation_used:
    print(f"  Escalation: {gate.escalation_reason}")


def _print_last(turn: ProfileChatResult | None) -> None:
  if turn is None:
    print("  (sin turnos aún)")
    return
  gate = turn.gate
  print("  --- Último turno — RAGE v2 ---")
  print(f"  Usuario   : {turn.user_text[:120]}")
  print(f"  Veredicto : {gate.verdict.value.upper()}  (acción={gate.action})")
  _print_gate_panel(gate)
  if turn.gate.blocked:
    print(f"  Respuesta : {turn.assistant_text[:200]}")
  print(_format_latency(turn))


def main() -> int:
  parser = argparse.ArgumentParser(
    description="RAGE product demo — perfiles + UserGate v2 + latencia por turno",
  )
  parser.add_argument(
    "--profile",
    default="restaurant",
    choices=list_profiles(),
    help="Perfil de empresa",
  )
  parser.add_argument("--list-profiles", action="store_true", help="Listar perfiles")
  parser.add_argument("--offline", action="store_true", help="Sin API — respuestas mock")
  parser.add_argument(
    "--full",
    action="store_true",
    help="Activa escalation judge en ALERT (pide API key)",
  )
  parser.add_argument("--model", default=None, help="Modelo asistente (override)")
  args = parser.parse_args()

  if args.list_profiles:
    print("Perfiles disponibles:")
    for pid in list_profiles():
      p = load_bot_profile(pid)
      print(f"  {pid:<12} {p.display_name}")
    return 0

  profile = load_bot_profile(args.profile)

  if not args.offline and args.full:
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
  bot = ProfileChatbot(
    profile=profile,
    model=model,
    escalate_on_alert=args.full,
  )
  show_latency = True
  verbose_rage = False
  last_turn: ProfileChatResult | None = None

  print()
  print("=" * 62)
  print(f"  RAGE Product Demo — {profile.display_name}")
  print(f"  Rol      : {profile.role}")
  print(f"  Propósito: {profile.purpose[:70]}...")
  print("  Motor    : RAGE v2 (ALERT continúa; CONTAIN bloquea)")
  if args.offline:
    print("  Modo     : OFFLINE")
  else:
    print(f"  Asistente: {model}")
    if args.full:
      print("  Escalation judge: ON (post-ALERT)")
  print("-" * 62)
  print("  /quit  /reset  /profile  /last  /latency  /verbose")
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

    turn = bot.handle_turn(
      user_text,
      offline=args.offline,
      use_escalation_api=args.full and not args.offline,
    )
    last_turn = turn

    if turn.gate.alert_banner and not turn.gate.blocked:
      print(f"\n[Sistema]> {turn.gate.alert_banner}")

    if turn.gate.blocked:
      print(f"\n[Sistema]> {turn.assistant_text}")
    else:
      body = turn.assistant_text
      if turn.gate.alert_banner and body.startswith(turn.gate.alert_banner):
        body = body[len(turn.gate.alert_banner) :].lstrip()
      print(f"\n{_short_name(profile)}> {body}")

    if verbose_rage or turn.gate.verdict.value in ("alert", "contain", "watch"):
      _print_gate_panel(turn.gate)
    if show_latency:
      print(_format_latency(turn))


if __name__ == "__main__":
  raise SystemExit(main())
