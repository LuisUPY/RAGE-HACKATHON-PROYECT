"""L4 — fuse layer signals into CLEAR / WATCH / ALERT / CONTAIN."""
from __future__ import annotations

from rage_core.v2.models import FusionResult, LayerSignalsV2, L3Signal, Verdict
from rage_core.v2.layers.l3_hints import FamilyHints

# Documented weights (match implementation)
_W_L0 = 55
_W_HINT_HIGH = 25
_W_TRAJECTORY = 30
_W_DRIFT = 15
_W_DOMAIN_VETO = -25

_T_CLEAR = 35
_T_WATCH = 55
_T_ALERT = 75


def fuse(signals: LayerSignalsV2) -> FusionResult:
  score = 0.0
  reasons: list[str] = []

  if signals.l0.hard_hit:
    score += _W_L0
    reasons.append(f"L0:{signals.l0.rule_id}")

  if FamilyHints.is_high_hint(signals.l3):
    score += _W_HINT_HIGH
    reasons.append(f"L3_hint:{signals.l3.hint_score:.2f}")
  elif FamilyHints.is_alert_hint(signals.l3):
    score += _W_HINT_HIGH * 0.5
    reasons.append(f"L3_hint_soft:{signals.l3.hint_score:.2f}")

  if signals.l2.escalation_detected:
    score += _W_TRAJECTORY
    reasons.append("L2_escalation")
  else:
    drift = max(signals.l2.step_drift, signals.l2.baseline_drift)
    if drift >= 0.72:
      score += _W_DRIFT
      reasons.append(f"L2_drift:{drift:.2f}")

  if signals.l1.domain_plausible:
    score += _W_DOMAIN_VETO
    reasons.append("L1_domain_plausible")

  score = max(0.0, min(100.0, score))

  if signals.l0.hard_hit:
    score = max(score, float(_T_ALERT))

  if score < _T_CLEAR:
    raw = Verdict.CLEAR
  elif score < _T_WATCH:
    raw = Verdict.WATCH
  elif score < _T_ALERT:
    raw = Verdict.ALERT
  else:
    raw = Verdict.CONTAIN

  # L3 hint alone cannot CONTAIN
  if raw == Verdict.CONTAIN and not signals.l0.hard_hit and not signals.l2.escalation_detected:
    if FamilyHints.is_high_hint(signals.l3) and signals.l2.trajectory_score < 0.55:
      raw = Verdict.ALERT
      reasons.append("hint_only_cap_alert")

  verdict = raw
  if raw == Verdict.CONTAIN and signals.l1.veto_contain:
    verdict = Verdict.ALERT
    reasons.append("L1_veto_contain")

  return FusionResult(score=score, verdict=verdict, raw_verdict=raw, reasons=reasons)
