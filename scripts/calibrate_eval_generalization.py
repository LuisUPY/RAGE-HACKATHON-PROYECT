"""Probe candidate generalization cases against L1+L2 (no judge) for recall calibration."""
from __future__ import annotations

import json
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


def _cases(entries: list[dict], prefix: str = "gen") -> list[BenchmarkCase]:
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


def _report(label: str, results) -> None:
    m = compute_metrics(results)
    fns = [r for r in results if r.outcome == "FN"]
    print(f"\n=== {label} ===")
    print(f"Recall: {m.recall:.1%} ({m.tp}/{m.tp + m.fn})  FP: {m.fp}  Acc: {m.accuracy:.1%}")
    for r in fns:
        l1 = r.signal.layer1.pattern_id if r.signal.layer1.matched else "-"
        l2 = f"{r.signal.layer2.score:.2f}" if r.signal.layer2.score else "-"
        print(f"  FN [{l1}|L2={l2}] {r.case.id}: {r.case.text[:90]}...")


def main() -> None:
    root = Path(__file__).parent.parent / "rage_core" / "kb" / "eval_generalization"
    holdout = json.loads((root / "holdout.json").read_text(encoding="utf-8"))
    scenarios_raw = json.loads((root / "scenarios.json").read_text(encoding="utf-8"))

    kb_texts = _kb_text_index()
    for e in holdout:
        if e["text"].lower().strip() in kb_texts:
            print(f"WARN overlap KB: {e['id']}")

    st = run_benchmark(_cases(holdout), use_judge=False, multi_turn=False)
    _report("Single-turn (L1+L2)", st)

    mt = run_multi_turn_benchmark(_scenarios(scenarios_raw), use_judge=False)
    _report("Multi-turn (L1+L2)", mt)

    combined = st + mt
    _report("Combined (L1+L2)", combined)


if __name__ == "__main__":
    main()
