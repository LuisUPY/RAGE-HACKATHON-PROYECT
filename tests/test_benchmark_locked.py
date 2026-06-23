"""Tests for frozen official holdout eval_locked_v1 (no calibrated recall band)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rage_core.benchmark.dataset import load_eval_holdout_dataset, load_eval_scenarios
from rage_core.benchmark.evaluator import compute_metrics, run_benchmark, run_multi_turn_benchmark

ROOT = Path(__file__).resolve().parent.parent
LOCKED_DIR = ROOT / "rage_core" / "kb" / "eval_locked_v1"
BASELINE_PATH = ROOT / "benchmarks" / "baseline_locked_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestLockedV1Dataset:
    def test_locked_v1_loads(self) -> None:
        cases = load_eval_holdout_dataset("locked_v1")
        scenarios = load_eval_scenarios("locked_v1")
        assert len(cases) >= 20
        assert len(scenarios) >= 8
        assert any(c.is_attack for c in cases)
        assert any(not c.is_attack for c in cases)

    def test_locked_v1_no_kb_overlap(self) -> None:
        kb_texts: set[str] = set()
        for name in ("threats.json", "benign.json"):
            path = ROOT / "rage_core" / "kb" / name
            for entry in json.loads(path.read_text(encoding="utf-8")):
                kb_texts.add(entry["text"].lower().strip())

        for case in load_eval_holdout_dataset("locked_v1"):
            assert case.text.lower().strip() not in kb_texts, (
                f"locked_v1 {case.id} duplicates KB text"
            )
        for scenario in load_eval_scenarios("locked_v1"):
            for turn in scenario.turns:
                assert turn.text.lower().strip() not in kb_texts, (
                    f"locked_v1 {scenario.id} turn duplicates KB text"
                )

    def test_locked_v1_manifest_integrity(self) -> None:
        manifest = json.loads((LOCKED_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
        for name, meta in manifest["files"].items():
            path = LOCKED_DIR / name
            assert path.is_file(), f"missing {name}"
            assert _sha256(path) == meta["sha256"], f"MANIFEST mismatch for {name}"

    def test_locked_v1_zero_false_positives(self) -> None:
        st = run_benchmark(load_eval_holdout_dataset("locked_v1"), use_judge=False, multi_turn=False)
        mt = run_multi_turn_benchmark(load_eval_scenarios("locked_v1"), use_judge=False)
        m = compute_metrics(st + mt)
        assert m.fp == 0, f"locked_v1 must not block benign (got {m.fp} FP)"

    def test_locked_v1_regression_snapshot(self) -> None:
        assert BASELINE_PATH.is_file(), "missing benchmarks/baseline_locked_v1.json"
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

        st = run_benchmark(load_eval_holdout_dataset("locked_v1"), use_judge=False, multi_turn=False)
        mt = run_multi_turn_benchmark(load_eval_scenarios("locked_v1"), use_judge=False)
        m = compute_metrics(st + mt)

        tol = baseline.get("tolerance", {})
        fp_max = int(tol.get("fp_max", 0))
        recall_abs = float(tol.get("recall_abs", 0.02))
        bm = baseline["metrics"]

        assert m.fp <= fp_max, f"FP {m.fp} > max {fp_max}"
        assert abs(m.recall - bm["recall"]) <= recall_abs, (
            f"recall {m.recall:.1%} vs baseline {bm['recall']:.1%}"
        )
        assert m.tp == bm["tp"]
        assert m.fn == bm["fn"]
        assert m.tn == bm["tn"]
        assert m.total == bm["total"]
