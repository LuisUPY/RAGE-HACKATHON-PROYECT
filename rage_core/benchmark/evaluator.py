"""
Benchmark evaluator — runs each labeled case through RAGE+Judge and compares
the result against the ground-truth label.

Verdict logic
─────────────
  RAGE+Judge says ATTACK when:
    • signal.layer1.matched  — deterministic L1 signature matched (e.g. DROP TABLE)
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

from rage_core.benchmark.dataset import BenchmarkCase
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
    judge_contribution: int = 0  # cases where judge caught what L1 missed


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


def _decide(signal: TurnSignal, use_judge: bool) -> bool:
    """Return True (attack) when L1 or (when use_judge) the LLM judge fired."""
    if signal.layer1.matched:
        return True
    if use_judge and signal.layer3.llm_flagged:
        return True
    return False


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

    # Judge contribution: cases where L1 did NOT match but judge still caught it
    judge_contribution = sum(
        1 for r in results
        if r.rage_verdict and not r.signal.layer1.matched and r.signal.layer3.llm_flagged
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
        judge_contribution=judge_contribution,
    )
