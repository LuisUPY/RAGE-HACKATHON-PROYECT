"""Regression tests for RAGE v2 on frozen eval_locked_v1."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rage_core.benchmark.dataset import load_eval_holdout_dataset, load_eval_scenarios
from rage_core.benchmark.v2_evaluator import (
    is_v2_attack_detected,
    run_v2_benchmark,
    run_v2_multi_turn_benchmark,
    v2_results_to_legacy_metrics,
)
from rage_core.v2.models import Verdict

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "benchmarks" / "baseline_locked_v2.json"


class TestLockedV1V2:
  def test_v2_locked_zero_false_positives(self) -> None:
    st = run_v2_benchmark(load_eval_holdout_dataset("locked_v1"))
    mt = run_v2_multi_turn_benchmark(load_eval_scenarios("locked_v1"))
    m = v2_results_to_legacy_metrics(st + mt)
    assert m.fp == 0, f"v2 must not flag benign (got {m.fp} FP)"

  def test_v2_fp_suite_never_contain_on_benign(self) -> None:
    from rage_core.v2.fp_corpus import load_fp_suite
    from rage_core.profiles.bot_profile import load_bot_profile
    from rage_core.v2.pipeline import PipelineV2

    for case in load_fp_suite():
      profile = load_bot_profile(case.profile_id)
      _, fusion = PipelineV2(profile).evaluate(case.text)
      assert fusion.verdict != Verdict.CONTAIN

  def test_v2_locked_regression_snapshot(self) -> None:
    assert BASELINE_PATH.is_file(), "missing benchmarks/baseline_locked_v2.json"
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    st = run_v2_benchmark(load_eval_holdout_dataset("locked_v1"))
    mt = run_v2_multi_turn_benchmark(load_eval_scenarios("locked_v1"))
    m = v2_results_to_legacy_metrics(st + mt)

    tol = baseline.get("tolerance", {})
    fp_max = int(tol.get("fp_max", 0))
    recall_abs = float(tol.get("recall_abs", 0.02))
    bm = baseline["metrics"]

    assert m.fp <= fp_max
    assert abs(m.recall - bm["recall"]) <= recall_abs
    assert m.tp == bm["tp"]
    assert m.fn == bm["fn"]
    assert m.tn == bm["tn"]
    assert m.total == bm["total"]

  def test_is_v2_attack_detected_alert_and_contain(self) -> None:
    from rage_core.v2.models import FusionResult

    assert is_v2_attack_detected(
      FusionResult(score=60, verdict=Verdict.ALERT, raw_verdict=Verdict.ALERT)
    )
    assert not is_v2_attack_detected(
      FusionResult(score=40, verdict=Verdict.WATCH, raw_verdict=Verdict.WATCH)
    )
