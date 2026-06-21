"""
Layer 4 — Decision Engine.

Fuses signals from Layers 1–3 into a single score (0–100) and assigns
a band: allow / warn / block.

Scoring weights (tunable via constructor):
  - Layer 1 hard-match:       +70 pts  (deterministic signature → almost certain attack)
  - Layer 2 RAG score:        up to +20 pts  (similarity to known attacks)
  - Layer 3 drift (blended):  up to +10 pts  (max of turn-to-turn and cumulative drift)
  - Layer 3 LLM flagged:      +10 bonus      (LLM judge confirmed escalation)

Band thresholds (adjustable):
  - score < 30  → allow
  - 30 ≤ score < 65  → warn
  - score ≥ 65  → block

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

    def __init__(self, block_threshold: float = 65.0, warn_threshold: float = 30.0) -> None:
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
        score = self._compute_score(l1, l2, l3)
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

    def _compute_score(self, l1: Layer1Signal, l2: Layer2Signal, l3: Layer3Signal) -> float:
        score = 0.0

        # Layer 1 — hard match
        if l1.matched:
            score += 70.0

        # Layer 2 — RAG similarity (0–1 → 0–20 pts)
        score += min(l2.score, 1.0) * 20.0

        # Layer 3 — blended drift: take the maximum of turn-to-turn and cumulative
        # drift so that both abrupt jumps AND gradual Crescendo trajectories are
        # captured in a single 0–10 pt contribution.
        blended_drift = max(l3.drift, l3.cumulative_drift)
        score += min(blended_drift, 1.0) * 10.0

        # Layer 3 — LLM judge bonus
        if l3.llm_flagged:
            score += 10.0

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

    # EWMA decay for session risk score
    _EWMA_ALPHA: float = 0.4
    # After this many consecutive WARNs → auto-BLOCK
    _RATCHET_TURNS: int = 3
    # EWMA thresholds for band elevation
    _SESSION_RISK_WARN_THRESHOLD: float = 0.25   # ALLOW → WARN if EWMA > this
    _SESSION_RISK_BLOCK_THRESHOLD: float = 0.55  # WARN  → BLOCK if EWMA > this

    def __init__(self) -> None:
        from rage_core.layers.layer1_rules import DeterministicPreFilter
        from rage_core.layers.layer2_rag import ThreatKBRetriever
        from rage_core.layers.layer3_semantic import DynamicSemanticFilter

        self._l1 = DeterministicPreFilter()
        self._l2 = ThreatKBRetriever()
        self._l3 = DynamicSemanticFilter()
        self._l4 = DecisionEngine()

    def evaluate(self, text: str, state: ConversationState) -> TurnSignal:
        t0 = time.perf_counter()

        l1_signal = self._l1.evaluate(text)
        l2_signal = self._l2.score(text)
        l3_signal = self._l3.evaluate(text, state)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        turn_signal = self._l4.decide(
            turn_index=state.turn_index,
            text=text,
            l1=l1_signal,
            l2=l2_signal,
            l3=l3_signal,
            latency_ms=round(latency_ms, 2),
        )

        # --- Crescendo-hardening: session-level ratchet ---

        # 1. Update rolling session-risk score (EWMA of normalised per-turn score)
        normalised_score = turn_signal.score / 100.0
        state.session_risk_score = (
            (1.0 - self._EWMA_ALPHA) * state.session_risk_score
            + self._EWMA_ALPHA * normalised_score
        )

        # 2. Band elevation based on accumulated session risk:
        #    - EWMA > SESSION_RISK_WARN_THRESHOLD  → at least WARN
        #    - EWMA > SESSION_RISK_BLOCK_THRESHOLD → BLOCK
        current_band = turn_signal.band
        if (
            state.session_risk_score > self._SESSION_RISK_BLOCK_THRESHOLD
            and current_band != Band.BLOCK
        ):
            current_band = Band.BLOCK
        elif (
            state.session_risk_score > self._SESSION_RISK_WARN_THRESHOLD
            and current_band == Band.ALLOW
        ):
            current_band = Band.WARN

        # 3. Consecutive-warn ratchet: N WARNs in a row → force BLOCK
        if current_band == Band.WARN:
            state.consecutive_warns += 1
        else:
            state.consecutive_warns = 0  # reset on ALLOW or BLOCK

        if state.consecutive_warns >= self._RATCHET_TURNS:
            current_band = Band.BLOCK

        # 4. Materialise band change (dataclass is immutable-style but we can replace)
        if current_band != turn_signal.band:
            turn_signal = dataclasses.replace(turn_signal, band=current_band)

        state.turn_index += 1
        state.signals.append(turn_signal)
        return turn_signal
