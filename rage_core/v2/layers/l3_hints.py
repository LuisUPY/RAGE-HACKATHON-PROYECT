"""L3 — KB family hints (high threshold; never sole CONTAIN trigger)."""
from __future__ import annotations

from rage_core.layers.layer2_rag import get_threat_kb_retriever
from rage_core.v2.models import L3Signal

_HINT_ALERT = 0.72
_HINT_HIGH = 0.82


class FamilyHints:
  """Wrap v1 RAG KB with v2 conservative thresholds."""

  def __init__(self) -> None:
    self._kb = get_threat_kb_retriever()

  def evaluate(self, text: str) -> L3Signal:
    sig = self._kb.score(text)
    hint_score = sig.score if sig.top_match_id else 0.0
    return L3Signal(
      hint_score=hint_score,
      top_match_id=sig.top_match_id,
      severity=sig.severity,
    )

  @staticmethod
  def is_high_hint(signal: L3Signal) -> bool:
    return signal.hint_score >= _HINT_HIGH

  @staticmethod
  def is_alert_hint(signal: L3Signal) -> bool:
    return signal.hint_score >= _HINT_ALERT
