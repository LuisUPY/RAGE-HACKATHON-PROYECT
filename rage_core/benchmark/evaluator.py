"""
Benchmark evaluator — runs each labeled case through RAGE+Judge and compares
the result against the ground-truth label.

Verdict logic
─────────────
  RAGE+Judge says ATTACK when:
    • signal.layer1.matched  — deterministic L1 signature matched (e.g. DROP TABLE)
    • signal.layer2.score ≥ 0.75 with a KB match — known attack paraphrase (L2 RAG)
    • signal.layer3.llm_flagged — the LLM judge confirmed escalation after drift

  RAGE+Judge says BENIGN otherwise.

  This means `use_judge=True` (default) uses both L1 and the LLM judge.
  `use_judge=False` relies solely on L1 — useful to measure the judge's contribution.

Each BenchmarkCase is evaluated independently (fresh ConversationState).
Multi-turn scenario context is intentionally discarded here so that each turn
is judged on its own text, making the results comparable with single-turn KB cases.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rage_core.benchmark.dataset import BenchmarkCase, BenchmarkScenario
from rage_core.layers.access_policy import RAG_ATTACK_THRESHOLD, is_attack_verdict, is_rag_confirmed_attack
from rage_core.layers.layer4_decision import DefensePipeline
from rage_core.models import ConversationState, TurnSignal


@dataclass
class CaseResult:
    """Result of evaluating a single BenchmarkCase."""

    case: BenchmarkCase
    signal: TurnSignal
    rage_verdict: bool    # True = RAGE+Judge says "attack"
    correct: bool         # True = rage_verdict matches ground truth (case.is_attack)

    @property
    def outcome(self) -> str:
        """Human-readable outcome: TP / TN / FP / FN."""
        if self.case.is_attack and self.rage_verdict:
            return "TP"
        if not self.case.is_attack and not self.rage_verdict:
            return "TN"
        if not self.case.is_attack and self.rage_verdict:
            return "FP"
        return "FN"


@dataclass
class BenchmarkMetrics:
    total: int
    correct: int
    tp: int   # attack correctly detected
    tn: int   # benign correctly allowed
    fp: int   # benign wrongly flagged as attack
    fn: int   # attack missed
    accuracy: float
    precision: float   # TP / (TP + FP)  — how trustworthy are positive detections
    recall: float      # TP / (TP + FN)  — how many attacks are caught
    f1: float
    false_positive_rate: float   # FP / (FP + TN) — usability cost
    l1_contribution: int = 0       # TP where L1 matched
    rag_contribution: int = 0      # TP where only L2 (RAG) caught it (L1 missed)
    judge_contribution: int = 0    # TP where only judge caught it (L1+L2 missed)


_BENIGN_PREAMBLE = "Can you show me the sales report for this quarter?"


def run_benchmark(
    cases: list[BenchmarkCase],
    use_judge: bool = True,
    multi_turn: bool = True,
) -> list[CaseResult]:
    """Evaluate each case through RAGE+Judge.

    Args:
        cases: Labeled benchmark cases (from load_dataset()).
        use_judge: When True, the LLM judge (Layer 3) is active via env vars.
                   When False, forces judge off — only L1 signatures count.
        multi_turn: When True (default), each attack case is preceded by a
                    benign preamble turn so Layer 3 can measure semantic drift
                    and the LLM judge actually gets called. Benign cases are
                    still evaluated as single-turn (benign-after-benign
                    produces low drift, so the judge is not triggered).

    Returns:
        List of CaseResult, one per case.
    """
    pipeline = DefensePipeline(
        apply_session_ratchet=False,
    )

    if not use_judge:
        pipeline._l3._use_llm = False  # noqa: SLF001

    results: list[CaseResult] = []
    for case in cases:
        state = ConversationState()

        if multi_turn and use_judge and case.is_attack:
            # Warm-up benign turn so L3 can measure drift on the attack turn.
            # A normal business request establishes the baseline embedding.
            pipeline.evaluate(_BENIGN_PREAMBLE, state)

        signal = pipeline.evaluate(case.text, state)
        rage_verdict = _decide(signal, use_judge)
        results.append(CaseResult(
            case=case,
            signal=signal,
            rage_verdict=rage_verdict,
            correct=(rage_verdict == case.is_attack),
        ))

    return results


def run_multi_turn_benchmark(
    scenarios: list[BenchmarkScenario],
    use_judge: bool = True,
) -> list[CaseResult]:
    """Evaluate multi-turn scenarios with shared conversation state per scenario.

    Each turn is judged in the context of all prior turns in that scenario —
    this is the realistic evaluation for Crescendo-style attacks where individual
    turns may look benign in isolation but escalate in conversation context.

    Scenarios are independent: fresh ConversationState per scenario.
    """
    pipeline = DefensePipeline(apply_session_ratchet=False)
    if not use_judge:
        pipeline._l3._use_llm = False  # noqa: SLF001

    results: list[CaseResult] = []
    for scenario in scenarios:
        state = ConversationState()
        for idx, turn in enumerate(scenario.turns):
            signal = pipeline.evaluate(turn.text, state)
            rage_verdict = _decide(signal, use_judge)
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
            results.append(CaseResult(
                case=case,
                signal=signal,
                rage_verdict=rage_verdict,
                correct=(rage_verdict == turn.is_attack),
            ))
    return results


def compute_scenario_metrics(
    scenarios: list[BenchmarkScenario],
    results: list[CaseResult],
) -> dict[str, dict]:
    """Per-scenario pass/fail: all attack turns detected, no benign FP."""
    by_scenario: dict[str, list[CaseResult]] = {}
    for r in results:
        # id format: mt:<scenario_id>:t<N>
        parts = r.case.id.split(":")
        scenario_key = parts[1] if len(parts) >= 2 else r.case.id
        by_scenario.setdefault(scenario_key, []).append(r)

    out: dict[str, dict] = {}
    for scenario in scenarios:
        rows = by_scenario.get(scenario.id, [])
        attack_rows = [r for r in rows if r.case.is_attack]
        benign_rows = [r for r in rows if not r.case.is_attack]
        attack_ok = all(r.correct for r in attack_rows) if attack_rows else True
        benign_ok = all(r.correct for r in benign_rows) if benign_rows else True
        out[scenario.id] = {
            "passed": attack_ok and benign_ok,
            "attack_turns": len(attack_rows),
            "attack_detected": sum(1 for r in attack_rows if r.rage_verdict),
            "benign_fp": sum(1 for r in benign_rows if r.rage_verdict),
        }
    return out


def _decide(signal: TurnSignal, use_judge: bool) -> bool:
    """Return True (attack) when L1, high-confidence L2, or the LLM judge fired."""
    return is_attack_verdict(signal, use_judge=use_judge)


def compute_metrics(results: list[CaseResult]) -> BenchmarkMetrics:
    """Compute classification metrics from a list of CaseResults."""
    total = len(results)
    if total == 0:
        return BenchmarkMetrics(0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)

    tp = sum(1 for r in results if r.outcome == "TP")
    tn = sum(1 for r in results if r.outcome == "TN")
    fp = sum(1 for r in results if r.outcome == "FP")
    fn = sum(1 for r in results if r.outcome == "FN")
    correct = tp + tn

    accuracy = correct / total
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    l1_contribution = sum(
        1 for r in results
        if r.outcome == "TP" and r.signal.layer1.matched
    )
    rag_contribution = sum(
        1 for r in results
        if r.outcome == "TP"
        and not r.signal.layer1.matched
        and is_rag_confirmed_attack(r.signal)
    )
    judge_contribution = sum(
        1 for r in results
        if r.outcome == "TP"
        and not r.signal.layer1.matched
        and not is_rag_confirmed_attack(r.signal)
        and r.signal.layer3.llm_flagged
    )

    return BenchmarkMetrics(
        total=total,
        correct=correct,
        tp=tp,
        tn=tn,
        fp=fp,
        fn=fn,
        accuracy=round(accuracy, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        false_positive_rate=round(fpr, 4),
        l1_contribution=l1_contribution,
        rag_contribution=rag_contribution,
        judge_contribution=judge_contribution,
    )


def compute_category_metrics(results: list[CaseResult]) -> dict[str, BenchmarkMetrics]:
    """Compute metrics grouped by case category for side-by-side comparison."""
    by_category: dict[str, list[CaseResult]] = {}
    for result in results:
        cat = result.case.category
        by_category.setdefault(cat, []).append(result)
    return {cat: compute_metrics(cat_results) for cat, cat_results in sorted(by_category.items())}


def analyze_failures(results: list[CaseResult]) -> list[dict]:
    """Return diagnostic rows for FP/FN holdout cases (open-world errors)."""
    from rage_core.layers.access_policy import is_rag_confirmed_attack

    rows: list[dict] = []
    for r in results:
        if r.correct:
            continue
        sig = r.signal
        rows.append({
            "id": r.case.id,
            "outcome": r.outcome,
            "label": "ATAQUE" if r.case.is_attack else "BENIGNO",
            "verdict": "ATAQUE" if r.rage_verdict else "BENIGNO",
            "l1": sig.layer1.pattern_id if sig.layer1.matched else None,
            "l2_score": round(sig.layer2.score, 3),
            "l2_match": sig.layer2.top_match_id,
            "l2_threshold": RAG_ATTACK_THRESHOLD,
            "judge": sig.layer3.llm_flagged,
            "category": r.case.category,
            "text": r.case.text[:80],
        })
    return rows
