"""Adapters between RAGE v2 signals and legacy v1 TurnSignal (demo metrics)."""
from __future__ import annotations

from rage_core.models import Band, Layer1Signal, Layer2Signal, Layer3Signal, TurnSignal
from rage_core.v2.models import FusionResult, LayerSignalsV2, Verdict


def signals_to_turn_signal(signals: LayerSignalsV2, fusion: FusionResult) -> TurnSignal:
  """Map v2 layer output to TurnSignal for AUC / demo compatibility."""
  band = Band.BLOCK if fusion.verdict == Verdict.CONTAIN else Band.ALLOW
  if fusion.verdict == Verdict.WATCH:
    band = Band.WARN
  if fusion.verdict == Verdict.ALERT:
    band = Band.WARN
  return TurnSignal(
    turn_index=signals.turn_index,
    text=signals.text,
    layer1=Layer1Signal(
      matched=signals.l0.hard_hit or signals.l0.medium_hit,
      pattern_id=signals.l0.rule_id or signals.l0.medium_rule_id,
    ),
    layer2=Layer2Signal(
      score=signals.l3.hint_score,
      top_match_id=signals.l3.top_match_id,
      severity=signals.l3.severity,
    ),
    layer3=Layer3Signal(
      drift=signals.l2.step_drift,
      suspicious=signals.l2.escalation_detected,
      llm_flagged=False,
      cumulative_drift=signals.l2.baseline_drift,
    ),
    score=fusion.score,
    band=band,
    latency_ms=signals.latency_ms,
  )
