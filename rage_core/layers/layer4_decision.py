"""
Layer 4 — Decision Engine.

Fuses signals from Layers 1–3 into a single score (0–100) and assigns
a band: allow / warn / block.

Scoring weights (tunable via constructor):
  - Layer 1 hard-match:  +70 pts  (deterministic signature → almost certain attack)
  - Layer 2 RAG score:   up to +20 pts  (similarity to known attacks)
  - Layer 3 drift:       up to +10 pts  (intent drift from previous turn)
  - Layer 3 LLM flagged: +10 bonus      (LLM judge confirmed escalation)

Band thresholds (adjustable):
  - score < 30  → allow
  - 30 ≤ score < 65  → warn
  - score ≥ 65  → block
"""
from __future__ import annotations

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

        # Layer 3 — drift signal (0–1 → 0–10 pts)
        score += min(l3.drift, 1.0) * 10.0

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
    """

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

        state.turn_index += 1
        state.signals.append(turn_signal)
        return turn_signal
