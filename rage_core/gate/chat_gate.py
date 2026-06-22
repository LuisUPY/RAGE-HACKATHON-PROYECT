"""Chat gate — RAGE detects, session judge adjudicates (multi-turn aware)."""
from __future__ import annotations

import time
from dataclasses import dataclass

from rage_core.judge.session_judge import JudgeDecision, RageBriefing, SessionJudge
from rage_core.layers.access_policy import (
    is_attack_verdict,
    is_confirmed_injection,
    is_multiturn_attack_verdict,
)
from rage_core.layers.layer4_decision import DefensePipeline
from rage_core.models import ConversationState, TurnSignal
from rage_core.profiles.bot_profile import BotProfile


@dataclass
class GateResult:
    """Final gate decision for one user turn."""

    allowed: bool
    action: str  # allow | block | deny
    signal: TurnSignal
    briefing: RageBriefing
    judge_used: bool
    judge_reason: str
    user_message: str
    rage_ms: float = 0.0
    judge_ms: float = 0.0

    @property
    def blocked(self) -> bool:
        return not self.allowed

    @property
    def block_message(self) -> str:
        if self.action == "deny":
            return (
                f"[RAGE+Juez] Acceso denegado — posible ataque multi-turno o inyección detectada. "
                f"({self.judge_reason})"
            )
        return (
            f"[RAGE+Juez] Mensaje bloqueado — revisión de seguridad. ({self.judge_reason})"
        )


def _needs_judge_review(signal: TurnSignal, policy_would_block: bool) -> bool:
    """Invoke session judge when RAGE sees risk beyond trivial allow."""
    if is_confirmed_injection(signal):
        return True
    if signal.layer3.suspicious:
        return True
    if policy_would_block:
        return True
    return False


class ChatGate:
    """
    Product foundation: configurable bot + RAGE pipeline + contextual judge.

    Flow per turn:
      1. RAGE L1–L4 evaluates with session state (drift, cumulative Δ).
      2. Build briefing — what RAGE detected.
      3. If flagged → session judge sees profile + history + briefing.
      4. ALLOW / BLOCK / DENY → gate chat or let assistant respond.
    """

    def __init__(
        self,
        profile: BotProfile,
        *,
        use_judge_api: bool = True,
        skip_l3_inline_judge: bool = True,
    ) -> None:
        self.profile = profile
        self.use_judge_api = use_judge_api
        self.pipeline = DefensePipeline(apply_session_ratchet=False)
        if skip_l3_inline_judge:
            self.pipeline._l3._use_llm = False  # noqa: SLF001 — session judge handles LLM
        self.judge = SessionJudge()
        self.state = ConversationState()
        self._prior_l2_peak = 0.0
        self._prior_drift_peak = 0.0
        self._history: list[dict[str, str]] = []

    def reset(self) -> None:
        self.state = ConversationState()
        self._prior_l2_peak = 0.0
        self._prior_drift_peak = 0.0
        self._history = []

    def evaluate(self, user_text: str) -> GateResult:
        turn_idx = self.state.turn_index
        rage_start = time.perf_counter()
        signal = self.pipeline.evaluate(user_text, self.state)
        rage_ms = (time.perf_counter() - rage_start) * 1000.0

        policy_block = is_multiturn_attack_verdict(
            signal,
            turn_index=turn_idx,
            prior_l2_peak=self._prior_l2_peak,
            prior_drift_peak=self._prior_drift_peak,
            session_risk=self.state.session_risk_score,
            use_judge=False,
        )

        briefing = RageBriefing.from_signal(
            signal,
            state=self.state,
            prior_l2_peak=self._prior_l2_peak,
            prior_drift_peak=self._prior_drift_peak,
            policy_would_block=policy_block,
        )

        self._update_peaks(signal)

        if not _needs_judge_review(signal, policy_block):
            self._history.append({"role": "user", "content": user_text})
            return GateResult(
                allowed=True,
                action="allow",
                signal=signal,
                briefing=briefing,
                judge_used=False,
                judge_reason="RAGE clear — no review needed",
                user_message=user_text,
                rage_ms=rage_ms,
                judge_ms=0.0,
            )

        # L1 hard confirm without API — fast path
        if is_confirmed_injection(signal) and not self.use_judge_api:
            self._history.append({"role": "user", "content": user_text})
            return GateResult(
                allowed=False,
                action="block",
                signal=signal,
                briefing=briefing,
                judge_used=False,
                judge_reason=f"L1/L2 confirmed ({signal.layer1.pattern_id or signal.layer2.top_match_id})",
                user_message=user_text,
                rage_ms=rage_ms,
                judge_ms=0.0,
            )

        judge_start = time.perf_counter()
        decision, reason = self.judge.review(
            profile=self.profile,
            briefing=briefing,
            current_message=user_text,
            history=self._history,
            use_api=self.use_judge_api,
        )
        judge_ms = (time.perf_counter() - judge_start) * 1000.0

        self._history.append({"role": "user", "content": user_text})

        if decision == JudgeDecision.ALLOW:
            return GateResult(
                allowed=True,
                action="allow",
                signal=signal,
                briefing=briefing,
                judge_used=True,
                judge_reason=reason,
                user_message=user_text,
                rage_ms=rage_ms,
                judge_ms=judge_ms,
            )

        action = "deny" if decision == JudgeDecision.DENY else "block"
        return GateResult(
            allowed=False,
            action=action,
            signal=signal,
            briefing=briefing,
            judge_used=True,
            judge_reason=reason,
            user_message=user_text,
            rage_ms=rage_ms,
            judge_ms=judge_ms,
        )

    def record_assistant(self, text: str) -> None:
        self._history.append({"role": "assistant", "content": text})

    def _update_peaks(self, signal: TurnSignal) -> None:
        self._prior_l2_peak = max(self._prior_l2_peak, signal.layer2.score)
        self._prior_drift_peak = max(
            self._prior_drift_peak,
            signal.layer3.drift,
            signal.layer3.cumulative_drift,
        )
