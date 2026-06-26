"""UserGate — v2 chat policy: only CONTAIN blocks the assistant."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from rage_core.profiles.bot_profile import BotProfile
from rage_core.v2.models import FusionResult, LayerSignalsV2, Verdict
from rage_core.v2.pipeline import PipelineV2

_ALERT_BANNER = (
  "[RAGE v2] Hemos detectado un patrón inusual en tu mensaje. "
  "El asistente puede responder, pero la sesión queda marcada para revisión."
)

_CONTAIN_MESSAGE = (
  "[RAGE v2] Mensaje bloqueado — posible intento de inyección o escalación detectada."
)


@dataclass
class UserGateResult:
  allowed: bool
  action: str  # allow | alert | contain
  verdict: Verdict
  score: float
  signals: LayerSignalsV2
  fusion: FusionResult
  alert_banner: str | None = None
  user_message: str = ""
  rage_ms: float = 0.0
  reasons: list[str] = field(default_factory=list)

  @property
  def blocked(self) -> bool:
    return not self.allowed

  @property
  def block_message(self) -> str:
    return _CONTAIN_MESSAGE


class UserGate:
  """Product gate: ALERT continues chat; CONTAIN blocks."""

  def __init__(self, profile: BotProfile) -> None:
    self.profile = profile
    self.pipeline = PipelineV2(profile)
    self._history: list[dict[str, str]] = []

  def reset(self) -> None:
    self.pipeline.reset()
    self._history = []

  def evaluate(self, user_text: str) -> UserGateResult:
    start = time.perf_counter()
    signals, fusion = self.pipeline.evaluate(user_text)
    rage_ms = (time.perf_counter() - start) * 1000.0

    if fusion.verdict == Verdict.CONTAIN:
      self._history.append({"role": "user", "content": user_text})
      return UserGateResult(
        allowed=False,
        action="contain",
        verdict=fusion.verdict,
        score=fusion.score,
        signals=signals,
        fusion=fusion,
        user_message=user_text,
        rage_ms=rage_ms,
        reasons=fusion.reasons,
      )

    alert_banner = None
    action = "allow"
    if fusion.verdict == Verdict.ALERT:
      alert_banner = _ALERT_BANNER
      action = "alert"

    self._history.append({"role": "user", "content": user_text})
    return UserGateResult(
      allowed=True,
      action=action,
      verdict=fusion.verdict,
      score=fusion.score,
      signals=signals,
      fusion=fusion,
      alert_banner=alert_banner,
      user_message=user_text,
      rage_ms=rage_ms,
      reasons=fusion.reasons,
    )

  def record_assistant(self, text: str) -> None:
    self._history.append({"role": "assistant", "content": text})

  @property
  def history(self) -> list[dict[str, str]]:
    return self._history
