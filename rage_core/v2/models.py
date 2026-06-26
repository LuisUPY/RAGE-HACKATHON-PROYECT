"""RAGE v2 data models — verdicts and per-layer signals."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
  CLEAR = "clear"
  WATCH = "watch"
  ALERT = "alert"
  CONTAIN = "contain"


@dataclass
class L0Signal:
  hard_hit: bool = False
  rule_id: str | None = None
  family: str | None = None
  medium_hit: bool = False
  medium_rule_id: str | None = None


@dataclass
class L1Signal:
  domain_plausible: bool = False
  veto_contain: bool = False
  domain_score: float = 0.0  # 0–1 alignment with profile


@dataclass
class L2Signal:
  step_drift: float = 0.0
  baseline_drift: float = 0.0
  trajectory_score: float = 0.0  # EWMA session risk 0–1
  escalation_detected: bool = False


@dataclass
class L3Signal:
  hint_score: float = 0.0
  top_match_id: str | None = None
  severity: str | None = None


@dataclass
class LayerSignalsV2:
  turn_index: int
  text: str
  l0: L0Signal
  l1: L1Signal
  l2: L2Signal
  l3: L3Signal
  latency_ms: float = 0.0


@dataclass
class FusionResult:
  score: float  # 0–100
  verdict: Verdict
  raw_verdict: Verdict  # before L1 veto downgrade
  reasons: list[str] = field(default_factory=list)


@dataclass
class ConversationStateV2:
  turn_index: int = 0
  turn_embeddings: list[list[float]] = field(default_factory=list)
  trajectory_ewma: float = 0.0
  drift_history: list[float] = field(default_factory=list)
  signals: list[LayerSignalsV2] = field(default_factory=list)
