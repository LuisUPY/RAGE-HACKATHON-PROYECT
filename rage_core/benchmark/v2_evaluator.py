"""RAGE v2 benchmark evaluator — locked holdout and multi-turn scenarios."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rage_core.benchmark.dataset import BenchmarkCase, BenchmarkScenario
from rage_core.benchmark.evaluator import BenchmarkMetrics, compute_metrics
from rage_core.profiles.bot_profile import BotProfile, load_bot_profile
from rage_core.v2.models import FusionResult, LayerSignalsV2, Verdict
from rage_core.v2.pipeline import PipelineV2

DEFAULT_BENCH_PROFILE = "practice"

OnV2Result = Callable[["V2CaseResult"], None]


@dataclass
class V2CaseResult:
  """Result of evaluating one labeled case with RAGE v2."""

  case: BenchmarkCase
  signals: LayerSignalsV2
  fusion: FusionResult
  rage_verdict: bool
  correct: bool

  @property
  def outcome(self) -> str:
    if self.case.is_attack and self.rage_verdict:
      return "TP"
    if not self.case.is_attack and not self.rage_verdict:
      return "TN"
    if not self.case.is_attack and self.rage_verdict:
      return "FP"
    return "FN"


def is_v2_attack_detected(fusion: FusionResult) -> bool:
  """Attack detected when verdict is ALERT or CONTAIN (WATCH is telemetry-only)."""
  return fusion.verdict in (Verdict.ALERT, Verdict.CONTAIN)


def run_v2_benchmark(
  cases: list[BenchmarkCase],
  *,
  profile: BotProfile | None = None,
  on_result: OnV2Result | None = None,
) -> list[V2CaseResult]:
  prof = profile or load_bot_profile(DEFAULT_BENCH_PROFILE)
  results: list[V2CaseResult] = []
  for case in cases:
    pipeline = PipelineV2(prof)
    signals, fusion = pipeline.evaluate(case.text)
    verdict = is_v2_attack_detected(fusion)
    row = V2CaseResult(
      case=case,
      signals=signals,
      fusion=fusion,
      rage_verdict=verdict,
      correct=(verdict == case.is_attack),
    )
    results.append(row)
    if on_result is not None:
      on_result(row)
  return results


def run_v2_multi_turn_benchmark(
  scenarios: list[BenchmarkScenario],
  *,
  profile: BotProfile | None = None,
  on_result: OnV2Result | None = None,
) -> list[V2CaseResult]:
  prof = profile or load_bot_profile(DEFAULT_BENCH_PROFILE)
  results: list[V2CaseResult] = []
  for scenario in scenarios:
    pipeline = PipelineV2(prof)
    for idx, turn in enumerate(scenario.turns):
      signals, fusion = pipeline.evaluate(turn.text)
      verdict = is_v2_attack_detected(fusion)
      desc = turn.description or f"Turn {idx} of {scenario.id}"
      if scenario.research_source:
        desc = f"{desc} [{scenario.research_source}]"
      case = BenchmarkCase(
        id=f"mt:{scenario.id}:t{idx}",
        text=turn.text,
        is_attack=turn.is_attack,
        source=scenario.source,
        category=scenario.category if turn.is_attack else "benign",
        description=desc,
      )
      row = V2CaseResult(
        case=case,
        signals=signals,
        fusion=fusion,
        rage_verdict=verdict,
        correct=(verdict == turn.is_attack),
      )
      results.append(row)
      if on_result is not None:
        on_result(row)
  return results


def to_legacy_case_result(row: V2CaseResult) -> CaseResult:
  """Convert one v2 row for shared CLI tables and metrics."""

  from rage_core.benchmark.evaluator import CaseResult
  from rage_core.models import Band, Layer1Signal, Layer2Signal, Layer3Signal, TurnSignal

  sig = TurnSignal(
    turn_index=row.signals.turn_index,
    text=row.case.text,
    layer1=Layer1Signal(matched=row.signals.l0.hard_hit, pattern_id=row.signals.l0.rule_id),
    layer2=Layer2Signal(score=row.signals.l3.hint_score, top_match_id=row.signals.l3.top_match_id),
    layer3=Layer3Signal(
      drift=row.signals.l2.step_drift,
      suspicious=row.signals.l2.escalation_detected,
      llm_flagged=False,
      cumulative_drift=row.signals.l2.baseline_drift,
    ),
    score=row.fusion.score,
    band=Band.BLOCK if row.fusion.verdict == Verdict.CONTAIN else Band.ALLOW,
    latency_ms=row.signals.latency_ms,
  )
  return CaseResult(
    case=row.case,
    signal=sig,
    rage_verdict=row.rage_verdict,
    correct=row.correct,
  )


def v2_results_to_legacy_metrics(results: list[V2CaseResult]) -> BenchmarkMetrics:
  """Map v2 rows to shared BenchmarkMetrics."""
  from rage_core.benchmark.evaluator import compute_metrics

  return compute_metrics([to_legacy_case_result(r) for r in results])
