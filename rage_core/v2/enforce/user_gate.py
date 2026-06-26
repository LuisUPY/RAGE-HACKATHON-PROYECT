"""UserGate — v2 chat policy: only CONTAIN blocks the assistant."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from rage_core.profiles.bot_profile import BotProfile
from rage_core.v2.judge.escalation import EscalationDecision, EscalationJudge
from rage_core.v2.models import FusionResult, LayerSignalsV2, Verdict
from rage_core.v2.pipeline import PipelineV2

_ALERT_BANNER = (
  "[RAGE] Hemos detectado un patrón inusual en tu mensaje. "
  "El asistente puede responder, pero la sesión queda marcada para revisión."
)

_CONTAIN_MESSAGE = (
  "[RAGE] Mensaje bloqueado — posible intento de inyección o escalación detectada."
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
  escalation_ms: float = 0.0
  escalation_used: bool = False
  escalation_reason: str = ""
  reasons: list[str] = field(default_factory=list)

  @property
  def blocked(self) -> bool:
    return not self.allowed

  @property
  def detected(self) -> bool:
    """Attack signal for benchmarks — ALERT or CONTAIN."""
    return self.verdict in (Verdict.ALERT, Verdict.CONTAIN) or self.blocked

  @property
  def block_message(self) -> str:
    return _CONTAIN_MESSAGE


class UserGate:
  """Product gate: ALERT continues chat; CONTAIN blocks; optional escalation on ALERT."""

  def __init__(
    self,
    profile: BotProfile,
    *,
    escalate_on_alert: bool = False,
  ) -> None:
    self.profile = profile
    self.escalate_on_alert = escalate_on_alert
    self.pipeline = PipelineV2(profile)
    self.escalation = EscalationJudge()
    self._history: list[dict[str, str]] = []

  def reset(self) -> None:
    self.pipeline.reset()
    self._history = []

  def evaluate(
    self,
    user_text: str,
    *,
    use_escalation_api: bool = False,
  ) -> UserGateResult:
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

    escalation_ms = 0.0
    escalation_used = False
    escalation_reason = ""

    if fusion.verdict == Verdict.ALERT and (self.escalate_on_alert or use_escalation_api):
      decision, escalation_reason, escalation_ms = self.escalation.review(
        profile=self.profile,
        signals=signals,
        fusion=fusion,
        current_message=user_text,
        history=self._history,
        use_api=use_escalation_api,
      )
      escalation_used = True
      if decision == EscalationDecision.CONTAIN:
        self._history.append({"role": "user", "content": user_text})
        return UserGateResult(
          allowed=False,
          action="contain",
          verdict=Verdict.CONTAIN,
          score=fusion.score,
          signals=signals,
          fusion=fusion,
          user_message=user_text,
          rage_ms=rage_ms,
          escalation_ms=escalation_ms,
          escalation_used=True,
          escalation_reason=escalation_reason,
          reasons=fusion.reasons + ["escalation_contain"],
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
      escalation_ms=escalation_ms,
      escalation_used=escalation_used,
      escalation_reason=escalation_reason,
      reasons=fusion.reasons,
    )

  def record_assistant(self, text: str) -> None:
    self._history.append({"role": "assistant", "content": text})

  @property
  def history(self) -> list[dict[str, str]]:
    return self._history
