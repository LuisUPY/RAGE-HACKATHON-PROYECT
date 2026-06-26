"""Configurable company chatbot — profile + RAGE v2 UserGate + optional LLM assistant."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from rage_core.llm.openai_compat import format_llm_api_error, get_llm_client, get_llm_model
from rage_core.profiles.bot_profile import BotProfile
from rage_core.v2.enforce.user_gate import UserGate, UserGateResult


@dataclass
class ProfileChatResult:
  user_text: str
  gate: UserGateResult
  assistant_text: str
  used_llm: bool = False
  assistant_ms: float = 0.0

  @property
  def rage_ms(self) -> float:
    return self.gate.rage_ms

  @property
  def escalation_ms(self) -> float:
    return self.gate.escalation_ms

  @property
  def total_ms(self) -> float:
    return self.rage_ms + self.escalation_ms + self.assistant_ms


@dataclass
class ProfileChatbot:
  """Product shell: BotProfile + UserGate + assistant LLM."""

  profile: BotProfile
  gate: UserGate = field(init=False)
  model: str = field(default_factory=get_llm_model)
  escalate_on_alert: bool = False

  def __post_init__(self) -> None:
    self.gate = UserGate(self.profile, escalate_on_alert=self.escalate_on_alert)

  def handle_turn(
    self,
    user_text: str,
    *,
    offline: bool = False,
    use_escalation_api: bool = False,
  ) -> ProfileChatResult:
    result = self.gate.evaluate(
      user_text,
      use_escalation_api=use_escalation_api and not offline,
    )
    if result.blocked:
      msg = result.block_message
      self.gate.record_assistant(msg)
      return ProfileChatResult(
        user_text=user_text,
        gate=result,
        assistant_text=msg,
        assistant_ms=0.0,
      )

    prefix = ""
    if result.alert_banner:
      prefix = result.alert_banner + "\n\n"

    client = None if offline else get_llm_client()
    if client is None:
      reply = prefix + self._offline_reply(user_text)
      self.gate.record_assistant(reply)
      return ProfileChatResult(
        user_text=user_text,
        gate=result,
        assistant_text=reply,
        used_llm=False,
        assistant_ms=0.0,
      )

    assistant_ms = 0.0
    try:
      messages = [
        {"role": "system", "content": self.profile.system_prompt},
        *self.gate.history[-10:],
      ]
      assistant_start = time.perf_counter()
      response = client.chat.completions.create(
        model=self.model,
        messages=messages,
        temperature=0.3,
        max_tokens=256,
      )
      assistant_ms = (time.perf_counter() - assistant_start) * 1000.0
      reply = prefix + (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
      reply = prefix + format_llm_api_error(exc, model=self.model)

    self.gate.record_assistant(reply)
    return ProfileChatResult(
      user_text=user_text,
      gate=result,
      assistant_text=reply,
      used_llm=True,
      assistant_ms=assistant_ms,
    )

  def _offline_reply(self, user_text: str) -> str:
    low = user_text.lower()
    pid = self.profile.profile_id
    if pid == "restaurant":
      if any(w in low for w in ("hora", "horario", "abierto")):
        return "Abrimos de 12:00 a 23:00 todos los días. ¿Te ayudo con una reserva?"
      if any(w in low for w in ("menú", "menu", "vegetar", "gluten")):
        return "Tenemos opciones vegetarianas y sin gluten. ¿Quieres ver el menú completo?"
      if "reserv" in low:
        return "Puedo anotar tu reserva. ¿Cuántas personas y a qué hora?"
      return "Soy el asistente del restaurante. Pregúntame por menú, horarios o reservas."
    if pid in ("support", "practice"):
      return "[Modo offline] Indica tu ticket INC-xxxx o describe el problema de CRM."
    if pid == "reports":
      return "[Modo offline] Puedes describir el reporte que quieres subir o resumir."
    return f"[{self.profile.display_name}] ¿En qué puedo ayudarte?"

  def reset(self) -> None:
    self.gate.reset()
