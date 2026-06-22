"""Probe generalization holdout against L1+L2 and optionally L1+L2+Judge."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rage_core.benchmark.evaluator import compute_metrics, run_benchmark, run_multi_turn_benchmark
from rage_core.benchmark.dataset import (
    BenchmarkCase,
    BenchmarkScenario,
    ScenarioTurn,
    _kb_text_index,
)
from rage_core.config.env_loader import ensure_env_loaded


def _cases(entries: list[dict]) -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            id=f"eval:{e['id']}",
            text=e["text"],
            is_attack=e["is_attack"],
            source="eval:generalization",
            category=e.get("category", "unknown"),
            description=e.get("description", ""),
        )
        for e in entries
    ]


def _scenarios(entries: list[dict]) -> list[BenchmarkScenario]:
    out: list[BenchmarkScenario] = []
    for e in entries:
        turns = [
            ScenarioTurn(text=t["text"], is_attack=t["is_attack"], description=t.get("description", ""))
            for t in e["turns"]
        ]
        out.append(
            BenchmarkScenario(
                id=e["id"],
                category=e.get("category", "unknown"),
                description=e.get("description", ""),
                turns=turns,
                source="eval:generalization",
                research_source=e.get("research_source", ""),
            )
        )
    return out


def _report(label: str, results, *, use_judge: bool) -> None:
    m = compute_metrics(results)
    fns = [r for r in results if r.outcome == "FN"]
    judge_hits = sum(
        1 for r in results
        if r.outcome == "TP" and r.signal.layer3.llm_flagged
        and not r.signal.layer1.matched
    )
    print(f"\n=== {label} ===")
    print(f"Recall: {m.recall:.1%} ({m.tp}/{m.tp + m.fn})  FP: {m.fp}  Acc: {m.accuracy:.1%}")
    if use_judge:
        print(f"Judge-only TP: {judge_hits}  L1: {m.l1_contribution}  L2: {m.rag_contribution}")
    for r in fns:
        l1 = r.signal.layer1.pattern_id if r.signal.layer1.matched else "-"
        l2 = f"{r.signal.layer2.score:.2f}" if r.signal.layer2.score else "-"
        j = "YES" if r.signal.layer3.llm_flagged else "no"
        print(f"  FN [L1={l1}|L2={l2}|J={j}] {r.case.id}: {r.case.text[:88]}...")


def _has_judge_keys() -> bool:
    ensure_env_loaded()
    for key in ("RAGE_LLM_API_KEY", "RAGE_NVIDIA_API_KEY", "OPENAI_API_KEY"):
        val = os.environ.get(key, "")
        if val and "PEGAR_AQUI" not in val:
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate eval_generalization recall")
    parser.add_argument(
        "--with-judge",
        action="store_true",
        help="Run with LLM judge (requires RAGE_LLM_API_KEY or OPENAI_API_KEY in env)",
    )
    args = parser.parse_args()
    use_judge = args.with_judge
    if use_judge and not _has_judge_keys():
        print("ERROR: --with-judge requires API keys in env (RAGE_LLM_API_KEY or OPENAI_API_KEY)")
        sys.exit(1)

    root = Path(__file__).parent.parent / "rage_core" / "kb" / "eval_generalization"
    holdout = json.loads((root / "holdout.json").read_text(encoding="utf-8"))
    scenarios_raw = json.loads((root / "scenarios.json").read_text(encoding="utf-8"))

    kb_texts = _kb_text_index()
    for e in holdout:
        if e["text"].lower().strip() in kb_texts:
            print(f"WARN overlap KB: {e['id']}")

    mode = "L1+L2+Judge" if use_judge else "L1+L2"
    st = run_benchmark(_cases(holdout), use_judge=use_judge, multi_turn=use_judge)
    _report(f"Single-turn ({mode})", st, use_judge=use_judge)

    mt = run_multi_turn_benchmark(_scenarios(scenarios_raw), use_judge=use_judge)
    _report(f"Multi-turn ({mode})", mt, use_judge=use_judge)

    combined = st + mt
    _report(f"Combined ({mode})", combined, use_judge=use_judge)


if __name__ == "__main__":
    main()
