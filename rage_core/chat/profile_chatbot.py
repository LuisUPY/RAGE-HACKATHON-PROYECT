"""Configurable company chatbot — profile + RAGE gate + optional LLM assistant."""
from __future__ import annotations

from dataclasses import dataclass, field

from rage_core.gate.chat_gate import ChatGate, GateResult
from rage_core.llm.openai_compat import format_llm_api_error, get_llm_client, get_llm_model
from rage_core.profiles.bot_profile import BotProfile


@dataclass
class ProfileChatResult:
    user_text: str
    gate: GateResult
    assistant_text: str
    used_llm: bool = False


@dataclass
class ProfileChatbot:
    """Minimal product shell: adapt profile, validate via RAGE+judge, then respond."""

    profile: BotProfile
    gate: ChatGate = field(init=False)
    model: str = field(default_factory=get_llm_model)

    def __post_init__(self) -> None:
        self.gate = ChatGate(self.profile, use_judge_api=True)

    def handle_turn(self, user_text: str, *, offline: bool = False) -> ProfileChatResult:
        if offline:
            self.gate.use_judge_api = False
        result = self.gate.evaluate(user_text)
        if result.blocked:
            msg = result.block_message
            self.gate.record_assistant(msg)
            return ProfileChatResult(user_text=user_text, gate=result, assistant_text=msg)

        client = None if offline else get_llm_client()
        if client is None:
            reply = self._offline_reply(user_text)
            self.gate.record_assistant(reply)
            return ProfileChatResult(
                user_text=user_text,
                gate=result,
                assistant_text=reply,
                used_llm=False,
            )

        try:
            messages = [
                {"role": "system", "content": self.profile.system_prompt},
                *self.gate._history[-10:],  # noqa: SLF001 — includes current user turn
            ]
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=400,
            )
            reply = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            reply = format_llm_api_error(exc, model=self.model)

        self.gate.record_assistant(reply)
        return ProfileChatResult(
            user_text=user_text,
            gate=result,
            assistant_text=reply,
            used_llm=True,
        )

    def _offline_reply(self, user_text: str) -> str:
        low = user_text.lower()
        pid = self.profile.profile_id
        if pid == "restaurant":
            if any(w in low for w in ("hora", "horario", "abierto")):
                return "Abrimos de 12:00 a 23:00 todos los días. ¿Te ayudo con una reserva?"
            if any(w in low for w in ("menú", "menu", "vegetar")):
                return "Tenemos opciones vegetarianas: risotto de setas y ensalada mediterránea."
            if "reserv" in low:
                return "Puedo anotar tu reserva. ¿Cuántas personas y a qué hora?"
            return "Soy el asistente del restaurante. Pregúntame por menú, horarios o reservas."
        if pid == "support":
            return "[Modo offline] Indica tu ticket INC-xxxx o describe el problema de CRM."
        if pid == "reports":
            return "[Modo offline] Puedes describir el reporte que quieres subir o resumir."
        return f"[{self.profile.display_name}] ¿En qué puedo ayudarte?"

    def reset(self) -> None:
        self.gate.reset()
