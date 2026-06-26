"""Tests for Track B product benchmark."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rage_core.benchmark.product_dataset import (
    count_product_turns,
    load_product_holdout,
    load_product_scenarios,
)
from rage_core.benchmark.product_evaluator import (
    ProductCaseResult,
    compute_product_metrics,
    export_run_json,
    run_product_benchmark,
    run_product_case,
    run_product_scenario,
)
from rage_core.profiles.bot_profile import load_bot_profile


class TestEvalProductDataset:
    def test_load_holdout_and_scenarios(self) -> None:
        cases = load_product_holdout()
        scenarios = load_product_scenarios()
        assert len(cases) >= 10
        assert len(scenarios) >= 2
        assert any(c.is_attack for c in cases)
        assert any(not c.is_attack for c in cases)

    def test_total_turn_count_near_twenty(self) -> None:
        total = count_product_turns()
        assert 18 <= total <= 22

    def test_cases_have_profile_ids(self) -> None:
        for case in load_product_holdout():
            assert case.profile_id in ("restaurant", "support", "reports", "practice")

    def test_scenarios_have_profile_ids(self) -> None:
        for scenario in load_product_scenarios():
            assert scenario.profile_id in ("restaurant", "support", "reports", "practice")
            assert len(scenario.turns) >= 2


class TestProductEvaluatorOffline:
    def test_drop_table_attack_blocked(self) -> None:
        cases = {c.id: c for c in load_product_holdout()}
        case = cases["prod-ho-003"]
        result = run_product_case(
            load_bot_profile(case.profile_id),
            case,
            use_judge_api=False,
        )
        assert result.outcome == "TP"
        assert result.rage_ms >= 0.0

    def test_benign_hours_allowed(self) -> None:
        cases = {c.id: c for c in load_product_holdout()}
        case = cases["prod-ho-b01"]
        result = run_product_case(
            load_bot_profile(case.profile_id),
            case,
            use_judge_api=False,
        )
        assert result.outcome == "TN"
        assert result.judge_ms == 0.0

    def test_multiturn_final_attack_blocked(self) -> None:
        scenarios = {s.id: s for s in load_product_scenarios()}
        scenario = scenarios["prod-mt-001"]
        results = run_product_scenario(
            load_bot_profile(scenario.profile_id),
            scenario,
            use_judge_api=False,
        )
        assert len(results) == 3
        assert results[0].outcome == "TN"
        assert results[-1].outcome == "TP"
        assert results[-1].blocked

    def test_full_offline_benchmark_completes(self) -> None:
        cases = load_product_holdout()
        scenarios = load_product_scenarios()
        results = run_product_benchmark(cases, scenarios, use_judge_api=False)
        assert len(results) == count_product_turns()
        assert all(r.rage_ms >= 0.0 for r in results)
        assert all(r.judge_ms >= 0.0 for r in results)


class TestProductMetrics:
    def test_metrics_from_synthetic_results(self) -> None:
        results = [
            ProductCaseResult(
                case_id="a1",
                profile_id="support",
                text="attack",
                is_attack=True,
                category="test",
                description="",
                blocked=True,
                detected=True,
                action="contain",
                verdict="contain",
                escalation_used=False,
                escalation_reason="",
                rage_would_contain=True,
                escalation_override=False,
                rage_ms=10.0,
                escalation_ms=0.0,
                turn_index=0,
            ),
            ProductCaseResult(
                case_id="b1",
                profile_id="support",
                text="benign",
                is_attack=False,
                category="benign",
                description="",
                blocked=False,
                detected=False,
                action="allow",
                verdict="clear",
                escalation_used=False,
                escalation_reason="clear",
                rage_would_contain=False,
                escalation_override=False,
                rage_ms=8.0,
                escalation_ms=0.0,
                turn_index=0,
            ),
            ProductCaseResult(
                case_id="b2",
                profile_id="support",
                text="benign",
                is_attack=False,
                category="benign",
                description="",
                blocked=True,
                detected=True,
                action="contain",
                verdict="contain",
                escalation_used=True,
                escalation_reason="override",
                rage_would_contain=False,
                escalation_override=True,
                rage_ms=9.0,
                escalation_ms=3.0,
                turn_index=0,
            ),
        ]
        m = compute_product_metrics(results)
        assert m.tp == 1
        assert m.tn == 1
        assert m.fp == 1
        assert m.recall == 1.0
        assert m.judge_override_count == 1
        assert m.judge_added_block == 1


class TestProductExport:
    def test_json_export_round_trip(self, tmp_path: Path) -> None:
        cases = load_product_holdout()[:2]
        results = run_product_benchmark(cases, [], use_judge_api=False)
        payload = export_run_json(
            results,
            mode="offline",
            profile_default="practice",
            run_id="test-run",
        )
        out = tmp_path / "run.json"
        out.write_text(json.dumps(payload), encoding="utf-8")
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["mode"] == "offline"
        assert len(loaded["cases"]) == 2
        assert "metrics" in loaded
        assert "latency" in loaded


class TestProductCli:
    def test_cli_offline_batch(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "rage_core.benchmark.product_cli", "--offline", "--batch"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert proc.returncode == 0
        assert "Product benchmark summary" in proc.stdout
        assert "recall=" in proc.stdout

    def test_analyze_bench_script(self, tmp_path: Path) -> None:
        cases = load_product_holdout()[:3]
        results = run_product_benchmark(cases, [], use_judge_api=False)
        payload = export_run_json(
            results,
            mode="offline",
            profile_default="practice",
            run_id="analyze-test",
        )
        json_path = tmp_path / "run.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")
        script = Path(__file__).parent.parent / "scripts" / "analyze_bench.py"
        proc = subprocess.run(
            [sys.executable, str(script), str(json_path)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "Security" in proc.stdout
        assert "Latency" in proc.stdout
        assert "Judge overrides" in proc.stdout
