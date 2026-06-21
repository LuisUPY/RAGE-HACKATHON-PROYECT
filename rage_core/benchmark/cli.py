"""
rage-bench — RAGE+Judge benchmark against the labeled threat KB.

Usage:
    uv run rage-bench                     # full benchmark with LLM judge
    uv run rage-bench --no-judge          # L1 only, no LLM calls
    uv run rage-bench --verbose           # show every case in the table
    uv run rage-bench --kb-only           # only KB cases (no scenario turns)
    uv run rage-bench --scenarios-only    # only scenario turns
    uv run rage-bench --filter fp         # show only False Positives
    uv run rage-bench --filter fn         # show only False Negatives (missed attacks)

Exit code: 0 if accuracy >= 80%, 1 otherwise.
"""
from __future__ import annotations

import argparse
import sys

from rage_core.benchmark.dataset import BenchmarkCase, dataset_summary, load_dataset
from rage_core.benchmark.evaluator import BenchmarkMetrics, CaseResult, compute_metrics, run_benchmark


# --------------------------------------------------------------------------- #
# Formatting helpers                                                            #
# --------------------------------------------------------------------------- #

_COL = {
    "id":     22,
    "text":   45,
    "label":   7,
    "verdict": 9,
    "l1":      4,
    "judge":   5,
    "score":   6,
    "result":  8,
}
_SEP = "─" * (sum(_COL.values()) + len(_COL) * 3)


def _truncate(s: str, width: int) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= width else s[: width - 2] + ".."


def _label(is_attack: bool) -> str:
    return "ATAQUE " if is_attack else "BENIGNO"


def _verdict(rage_verdict: bool) -> str:
    return "ATAQUE   " if rage_verdict else "BENIGNO  "


def _result_cell(outcome: str) -> str:
    marks = {"TP": "✓ TP", "TN": "✓ TN", "FP": "✗ FP", "FN": "✗ FN"}
    return marks.get(outcome, outcome)


def _print_header() -> None:
    print(
        f"{'ID':<{_COL['id']}} | "
        f"{'Texto':<{_COL['text']}} | "
        f"{'Label':<{_COL['label']}} | "
        f"{'RAGE+Juez':<{_COL['verdict']}} | "
        f"{'L1':<{_COL['l1']}} | "
        f"{'Juez':<{_COL['judge']}} | "
        f"{'Score':<{_COL['score']}} | "
        f"{'Resultado':<{_COL['result']}}"
    )
    print(_SEP)


def _print_row(r: CaseResult) -> None:
    print(
        f"{_truncate(r.case.id, _COL['id']):<{_COL['id']}} | "
        f"{_truncate(r.case.text, _COL['text']):<{_COL['text']}} | "
        f"{_label(r.case.is_attack):<{_COL['label']}} | "
        f"{_verdict(r.rage_verdict):<{_COL['verdict']}} | "
        f"{'YES' if r.signal.layer1.matched else 'no':<{_COL['l1']}} | "
        f"{'YES' if r.signal.layer3.llm_flagged else 'no':<{_COL['judge']}} | "
        f"{r.signal.score:<{_COL['score']}.1f} | "
        f"{_result_cell(r.outcome)}"
    )


def _print_metrics(m: BenchmarkMetrics, use_judge: bool) -> None:
    print()
    print(_SEP)
    print(f"  Total casos  : {m.total}")
    print(f"  Aciertos     : {m.correct}  ({m.accuracy * 100:.1f}%)")
    print()
    print(f"  TP (ataque detectado)  : {m.tp}")
    print(f"  TN (benigno permitido) : {m.tn}")
    print(f"  FP (falso positivo)    : {m.fp}  — bloqueados sin razón")
    print(f"  FN (ataque perdido)    : {m.fn}  — ataques que pasaron")
    print()
    print(f"  Accuracy   : {m.accuracy * 100:.1f}%")
    print(f"  Precision  : {m.precision * 100:.1f}%  (de lo que se bloquea, cuánto era real)")
    print(f"  Recall     : {m.recall * 100:.1f}%  (de los ataques, cuántos se detectaron)")
    print(f"  F1         : {m.f1 * 100:.1f}%")
    print(f"  FP rate    : {m.false_positive_rate * 100:.1f}%  (falsos positivos / total benignos)")
    if use_judge:
        print(f"  Juez +catch: {m.judge_contribution}  (ataques que solo el juez detectó)")
    print(_SEP)


def _filter_results(
    results: list[CaseResult],
    filter_arg: str | None,
) -> list[CaseResult]:
    if filter_arg is None:
        return results
    f = filter_arg.upper()
    return [r for r in results if r.outcome == f]


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE+Judge benchmark — compara predicciones contra KB ground-truth"
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Desactivar LLM judge; usar solo L1 (sin llamadas a API)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar todos los casos en la tabla (por defecto solo muestra fallos)",
    )
    parser.add_argument(
        "--kb-only",
        action="store_true",
        help="Usar solo los 33 casos de la KB (no los turnos de escenarios)",
    )
    parser.add_argument(
        "--scenarios-only",
        action="store_true",
        help="Usar solo los turnos de los escenarios (no la KB)",
    )
    parser.add_argument(
        "--filter",
        metavar="OUTCOME",
        choices=["tp", "tn", "fp", "fn", "TP", "TN", "FP", "FN"],
        help="Mostrar solo un tipo de resultado: tp / tn / fp / fn",
    )
    args = parser.parse_args()

    use_judge = not args.no_judge
    include_kb = not args.scenarios_only
    include_scenarios = not args.kb_only

    # Load dataset
    cases = load_dataset(include_kb=include_kb, include_scenarios=include_scenarios)
    if not cases:
        print("ERROR: dataset vacío.", file=sys.stderr)
        return 1

    summary = dataset_summary(cases)
    print()
    print("=" * (sum(_COL.values()) + len(_COL) * 3))
    print("  RAGE+Judge Benchmark")
    print(f"  Dataset: {summary['total']} casos  "
          f"({summary['attacks']} ataques / {summary['benign']} benignos)")
    print(f"  Juez LLM: {'ACTIVO' if use_judge else 'DESACTIVADO (solo L1)'}")
    if use_judge:
        from rage_core.llm.openai_compat import get_judge_model, llm_judge_enabled
        judge_ready = llm_judge_enabled()
        model = get_judge_model("nvidia/llama-3.1-nemotron-nano-8b-v1")
        print(f"  Modelo juez: {model}  (configurado: {'SI' if judge_ready else 'NO — activa RAGE_USE_LLM_JUDGE=1'})")
    print("=" * (sum(_COL.values()) + len(_COL) * 3))
    print()

    # Run evaluation
    print("Evaluando casos...", end=" ", flush=True)
    results = run_benchmark(cases, use_judge=use_judge)
    print(f"OK ({len(results)} casos)")
    print()

    # Filter for display
    display = _filter_results(results, args.filter)
    if not args.verbose and args.filter is None:
        # Default: show only failures
        display = [r for r in results if not r.correct]

    if display:
        _print_header()
        for r in display:
            _print_row(r)
        if not args.verbose and args.filter is None:
            print()
            print(f"  (mostrando {len(display)} fallos de {len(results)} casos — usa --verbose para ver todos)")

    # Metrics
    metrics = compute_metrics(results)
    _print_metrics(metrics, use_judge)

    # Exit code
    return 0 if metrics.accuracy >= 0.80 else 1


if __name__ == "__main__":
    raise SystemExit(main())
