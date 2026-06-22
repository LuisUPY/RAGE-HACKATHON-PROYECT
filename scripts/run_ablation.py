#!/usr/bin/env python3
"""Ablation study on eval_generalization holdout — honest layer contribution."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rage_core.benchmark.dataset import load_eval_holdout_dataset, load_eval_scenarios
from rage_core.benchmark.evaluator import (
    CaseResult,
    compute_metrics,
    run_benchmark,
    run_multi_turn_benchmark,
)
from rage_core.layers.access_policy import is_confirmed_injection, is_multiturn_attack_verdict
from rage_core.layers.layer4_decision import DefensePipeline
from rage_core.models import ConversationState


def _l1_only(st_cases, mt_scenarios) -> list[CaseResult]:
    from rage_core.benchmark.evaluator import CaseResult as CR
    from rage_core.benchmark.dataset import BenchmarkCase

    pipe = DefensePipeline(apply_session_ratchet=False)
    pipe._l3._use_llm = False  # noqa: SLF001
    out: list[CaseResult] = []
    for case in st_cases:
        state = ConversationState()
        signal = pipe.evaluate(case.text, state)
        verdict = signal.layer1.matched
        out.append(CR(case=case, signal=signal, rage_verdict=verdict, correct=verdict == case.is_attack))
    for scenario in mt_scenarios:
        state = ConversationState()
        for idx, turn in enumerate(scenario.turns):
            signal = pipe.evaluate(turn.text, state)
            verdict = signal.layer1.matched
            case = BenchmarkCase(
                id=f"mt:{scenario.id}:t{idx}",
                text=turn.text,
                is_attack=turn.is_attack,
                source=scenario.source,
                category=scenario.category if turn.is_attack else "benign",
                description=turn.description or "",
            )
            out.append(CR(case=case, signal=signal, rage_verdict=verdict, correct=verdict == turn.is_attack))
    return out


def _l1_l2_confirmed(st_cases, mt_scenarios) -> list[CaseResult]:
    from rage_core.benchmark.evaluator import CaseResult as CR
    from rage_core.benchmark.dataset import BenchmarkCase

    pipe = DefensePipeline(apply_session_ratchet=False)
    pipe._l3._use_llm = False  # noqa: SLF001
    out: list[CaseResult] = []
    for case in st_cases:
        state = ConversationState()
        signal = pipe.evaluate(case.text, state)
        verdict = is_confirmed_injection(signal)
        out.append(CR(case=case, signal=signal, rage_verdict=verdict, correct=verdict == case.is_attack))
    for scenario in mt_scenarios:
        state = ConversationState()
        prior_l2, prior_drift = 0.0, 0.0
        for idx, turn in enumerate(scenario.turns):
            signal = pipe.evaluate(turn.text, state)
            verdict = is_multiturn_attack_verdict(
                signal,
                turn_index=idx,
                prior_l2_peak=prior_l2,
                prior_drift_peak=prior_drift,
                session_risk=state.session_risk_score,
                use_judge=False,
            )
            prior_l2 = max(prior_l2, signal.layer2.score)
            prior_drift = max(prior_drift, signal.layer3.drift, signal.layer3.cumulative_drift)
            case = BenchmarkCase(
                id=f"mt:{scenario.id}:t{idx}",
                text=turn.text,
                is_attack=turn.is_attack,
                source=scenario.source,
                category=scenario.category if turn.is_attack else "benign",
                description=turn.description or "",
            )
            out.append(CR(case=case, signal=signal, rage_verdict=verdict, correct=verdict == turn.is_attack))
    return out


def _print_row(name: str, results: list[CaseResult]) -> None:
    m = compute_metrics(results)
    print(
        f"{name:<28} recall={m.recall:6.1%}  precision={m.precision:6.1%}  "
        f"FP={m.fp}  FN={m.fn}  acc={m.accuracy:.1%}"
    )


def main() -> int:
    st = load_eval_holdout_dataset("generalization")
    mt = load_eval_scenarios("generalization")

    print("")
    print("=" * 72)
    print("  ABLATION — eval_generalization holdout (60 cases combined)")
    print("=" * 72)
    print(f"{'Config':<28} {'recall':>8}  {'precision':>10}  FP   FN")
    print("-" * 72)

    _print_row("L1 only (regex)", _l1_only(st, mt))
    _print_row("L1+L2+MT policy (default)", _l1_l2_confirmed(st, mt))

    st_res = run_benchmark(st, use_judge=False, multi_turn=False)
    mt_res = run_multi_turn_benchmark(mt, use_judge=False)
    _print_row("ST isolated + MT policy", st_res + mt_res)

    print("-" * 72)
    print("Note: default benchmark ST path evaluates each case without MT context.")
    print("      Full combined mode uses run-bench-generalization.sh (recommended).")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
