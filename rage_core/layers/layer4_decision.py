"""
Layer 4 — Decision Engine.

Fuses signals from Layers 1–3 into a single score (0–100) and assigns
a band: allow / warn / block.

Scoring weights (implemented in `_compute_score`):
  - Layer 1 hard-match:       +70 pts
  - Layer 2 RAG score:        up to +22 pts  (similarity × 22)
  - Layer 3 drift (blended):  up to +15 pts  (max of turn-to-turn and cumulative drift)
  - Layer 3 cumulative bonus: +3 pts when cumulative_drift > 0.92 (turn ≥ 2)
  - Layer 3 LLM flagged:      +5 pts (nudge only — block via access_policy)

Band thresholds (adjustable):
  - score < 48  → allow
  - 48 ≤ score < 82  → warn
  - score ≥ 82  → block

Crescendo-hardening — session-level ratchet (DefensePipeline):
  - A rolling suspicion score (EWMA of per-turn normalised scores) accumulates
    across turns.  Moderate-risk turns that each individually stay below the
    warn threshold can still trip the ratchet if the EWMA climbs high enough.
  - After ``ratchet_turns`` consecutive WARN-band turns the band is
    automatically elevated to BLOCK, preventing slow-escalation bypasses where
    no single turn looks suspicious enough on its own.
"""
from __future__ import annotations

import dataclasses
import time

from rage_core.models import (
    Band,
    ConversationState,
    Layer1Signal,
    Layer2Signal,
    Layer3Signal,
    TurnSignal,
)


class DecisionEngine:
    """Layer 4: fuses layer signals into a final score and band.

    Args:
        block_threshold: Score ≥ this → block.  Default 65.
        warn_threshold:  Score ≥ this → warn.   Default 30.
    """

    def __init__(self, block_threshold: float = 82.0, warn_threshold: float = 48.0) -> None:
        self._block_th = block_threshold
        self._warn_th = warn_threshold

    def decide(
        self,
        turn_index: int,
        text: str,
        l1: Layer1Signal,
        l2: Layer2Signal,
        l3: Layer3Signal,
        latency_ms: float,
    ) -> TurnSignal:
        score = self._compute_score(turn_index, l1, l2, l3)
        band = self._band(score)
        return TurnSignal(
            turn_index=turn_index,
            text=text,
            layer1=l1,
            layer2=l2,
            layer3=l3,
            score=score,
            band=band,
            latency_ms=latency_ms,
        )

    # ----------------------------------------------------------------------- #
    # Internals                                                                #
    # ----------------------------------------------------------------------- #

    def _compute_score(
        self,
        turn_index: int,
        l1: Layer1Signal,
        l2: Layer2Signal,
        l3: Layer3Signal,
    ) -> float:
        score = 0.0

        # Layer 1 — hard match
        if l1.matched:
            score += 70.0

        # Layer 2 — RAG similarity (0–1 → 0–22 pts)
        score += min(l2.score, 1.0) * 22.0

        # Layer 3 — blended drift (0–15 pts)
        blended_drift = max(l3.drift, l3.cumulative_drift)
        score += min(blended_drift, 1.0) * 15.0

        # Crescendo bonus — only on strong sustained migration
        if turn_index >= 2 and l3.cumulative_drift > 0.92:
            score += 3.0

        # Layer 3 — LLM judge bonus (small nudge, not auto-block)
        if l3.llm_flagged:
            score += 5.0

        return round(min(score, 100.0), 2)

    def _band(self, score: float) -> Band:
        if score >= self._block_th:
            return Band.BLOCK
        if score >= self._warn_th:
            return Band.WARN
        return Band.ALLOW


# --------------------------------------------------------------------------- #
# Full pipeline (convenience wrapper)                                          #
# --------------------------------------------------------------------------- #


class DefensePipeline:
    """Orchestrates the 4-layer cascade for a multi-turn conversation.

    Usage::

        pipeline = DefensePipeline()
        state = ConversationState()
        for turn_text in conversation:
            signal = pipeline.evaluate(turn_text, state)
            if signal.band == Band.BLOCK:
                ...

    Crescendo-hardening parameters
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ``ewma_alpha`` controls how quickly the rolling session-risk score reacts
    to new signals.  Higher values (→ 1.0) weight recent turns more; lower
    values (→ 0.0) produce a slower-moving average.

    ``ratchet_turns`` is the number of consecutive WARN-band turns required
    before the pipeline automatically elevates the band to BLOCK.  This prevents
    a Crescendo attacker from staying perpetually in the warn zone.

    ``session_risk_block_threshold`` is the EWMA session-risk level (0–1) above
    which any otherwise-ALLOWed turn is elevated to WARN, and above
    ``session_risk_warn_threshold`` the entire band is elevated to BLOCK.
    """

    # Pragmatic defaults: maximize LLM/tool use; gateway enforces data boundaries.
    _EWMA_ALPHA: float = 0.30
    _RATCHET_TURNS: int = 6
    _SESSION_RISK_WARN_THRESHOLD: float = 0.42
    _SESSION_RISK_BLOCK_THRESHOLD: float = 0.72

    def __init__(
        self,
        ewma_alpha: float | None = None,
        ratchet_turns: int | None = None,
        session_risk_warn_threshold: float | None = None,
        session_risk_block_threshold: float | None = None,
        warn_blocks_tools: bool = False,
        apply_session_ratchet: bool = False,
    ) -> None:
        from rage_core.layers.layer1_rules import DeterministicPreFilter
        from rage_core.layers.layer2_rag import get_threat_kb_retriever
        from rage_core.layers.layer3_semantic import DynamicSemanticFilter

        # Instance-level overrides (fall back to class defaults if not provided)
        self.ewma_alpha = ewma_alpha if ewma_alpha is not None else self._EWMA_ALPHA
        self.ratchet_turns = ratchet_turns if ratchet_turns is not None else self._RATCHET_TURNS
        self.session_risk_warn_threshold = (
            session_risk_warn_threshold
            if session_risk_warn_threshold is not None
            else self._SESSION_RISK_WARN_THRESHOLD
        )
        self.session_risk_block_threshold = (
            session_risk_block_threshold
            if session_risk_block_threshold is not None
            else self._SESSION_RISK_BLOCK_THRESHOLD
        )
        self.warn_blocks_tools = warn_blocks_tools
        self.apply_session_ratchet = apply_session_ratchet

        self._l1 = DeterministicPreFilter()
        self._l2 = get_threat_kb_retriever()
        self._l3 = DynamicSemanticFilter()
        self._l4 = DecisionEngine()

    def evaluate(self, text: str, state: ConversationState) -> TurnSignal:
        from rage_core.layers.access_policy import is_rag_confirmed_from_l2

        t0 = time.perf_counter()

        l1_signal = self._l1.evaluate(text)
        l2_signal = self._l2.score(text)
        skip_judge = l1_signal.matched or is_rag_confirmed_from_l2(l2_signal)
        l3_signal = self._l3.evaluate(text, state, skip_llm_judge=skip_judge)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        turn_signal = self._l4.decide(
            turn_index=state.turn_index,
            text=text,
            l1=l1_signal,
            l2=l2_signal,
            l3=l3_signal,
            latency_ms=round(latency_ms, 2),
        )

        # --- Session ratchet (optional; off by default for chat / injection-only policy) ---
        if self.apply_session_ratchet:
            normalised_score = turn_signal.score / 100.0
            state.session_risk_score = (
                (1.0 - self.ewma_alpha) * state.session_risk_score
                + self.ewma_alpha * normalised_score
            )

            current_band = turn_signal.band
            if (
                state.session_risk_score > self.session_risk_block_threshold
                and current_band != Band.BLOCK
            ):
                current_band = Band.BLOCK
            elif (
                state.session_risk_score > self.session_risk_warn_threshold
                and current_band == Band.ALLOW
            ):
                current_band = Band.WARN

            if current_band == Band.WARN:
                state.consecutive_warns += 1
            else:
                state.consecutive_warns = 0

            if state.consecutive_warns >= self.ratchet_turns:
                current_band = Band.BLOCK

            if current_band in (Band.WARN, Band.BLOCK):
                state.had_warn_or_block = True

            if current_band != turn_signal.band:
                turn_signal = dataclasses.replace(turn_signal, band=current_band)
        else:
            # Still track a light session score for gateway telemetry only.
            state.session_risk_score = (
                0.9 * state.session_risk_score
                + 0.1 * (turn_signal.score / 100.0)
            )

        state.turn_index += 1
        state.signals.append(turn_signal)
        return turn_signal
