"""
rage-bench — RAGE+Judge benchmark against the labeled threat KB.

Usage:
    uv run rage-bench --demo              # escenario aleatorio con RAGE+Juez (requiere API keys)
    uv run rage-bench                     # benchmark completo con LLM judge
    uv run rage-bench --no-judge          # L1 only, no LLM calls
    uv run rage-bench --verbose           # show every case in the table
    uv run rage-bench --kb-only           # only KB cases (no scenario turns)
    uv run rage-bench --scenarios-only    # only scenario turns
    uv run rage-bench --filter fp         # show only False Positives
    uv run rage-bench --filter fn         # show only False Negatives (missed attacks)
    uv run rage-bench --by-category       # breakdown por categoría (comparar familias)
    uv run rage-bench --attacks-kb-only   # solo threats.json (58 ataques)
    uv run rage-bench --benign-kb-only    # solo benign.json (20 benignos)
    uv run rage-bench --holdout           # evaluación abierta: casos NO en la KB (generalización)
    uv run rage-bench --holdout --verbose # ver cada caso holdout + errores detallados
    uv run rage-bench --multi-turn         # escenarios multi-turno con contexto acumulado
    uv run rage-bench --multi-turn --verbose
    uv run rage-bench --holdout --eval-set practice      # dataset de práctica (solo casos nuevos)
    uv run rage-bench --multi-turn --eval-set practice   # escenarios de práctica multi-turno
    uv run rage-bench --holdout --eval-set open_v3       # benchmark abierto v3 (parafraseos)
    uv run rage-bench --multi-turn --eval-set open_v3    # multi-turno open v3

Exit code: 0 if accuracy >= 80% (closed KB). Holdout always exits 0 (métricas informativas).
"""
from __future__ import annotations

import argparse
import random
import sys

from rage_core.benchmark.dataset import (
    BenchmarkCase,
    dataset_summary,
    load_dataset,
    load_holdout_dataset,
    load_holdout_scenarios,
    load_eval_holdout_dataset,
    load_eval_scenarios,
    scenario_summary,
)
from rage_core.benchmark.evaluator import (
    BenchmarkMetrics,
    CaseResult,
    analyze_failures,
    compute_category_metrics,
    compute_metrics,
    compute_scenario_metrics,
    run_benchmark,
    run_multi_turn_benchmark,
)


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
    print()
    print(f"  Detección por capa (solo TP):")
    print(f"    L1 firmas     : {m.l1_contribution}")
    print(f"    L2 RAG (KB)   : {m.rag_contribution}  (similitud ≥ umbral, sin L1)")
    if use_judge:
        print(f"    L3 Juez LLM   : {m.judge_contribution}  (solo juez, sin L1/L2)")
    print(_SEP)


def _print_holdout_failures(results: list[CaseResult]) -> None:
    failures = analyze_failures(results)
    if not failures:
        return
    print()
    print("  Errores en evaluación abierta (casos NO vistos en la KB):")
    print(f"  {'ID':<22} {'Err':<4} {'Label':<8} {'L1':<8} {'L2':>5} {'KB~':<8} {'Categoría':<20}")
    print("  " + "─" * 78)
    for row in failures:
        l1 = row["l1"] or "—"
        kb = row["l2_match"] or "—"
        print(
            f"  {row['id']:<22} {row['outcome']:<4} {row['label']:<8} "
            f"{l1:<8} {row['l2_score']:>5} {kb:<8} {row['category']:<20}"
        )
        print(f"    > {row['text']}")
    print(_SEP)


def _print_category_metrics(by_category: dict[str, BenchmarkMetrics]) -> None:
    print()
    print("  Desglose por categoría:")
    print(f"  {'Categoría':<28} {'N':>4}  {'Acc':>6}  {'Rec':>6}  {'FP':>3}  {'FN':>3}")
    print("  " + "─" * 58)
    for category, m in by_category.items():
        print(
            f"  {category:<28} {m.total:>4}  "
            f"{m.accuracy * 100:>5.1f}%  {m.recall * 100:>5.1f}%  "
            f"{m.fp:>3}  {m.fn:>3}"
        )
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
# Demo mode — single random case with full layer breakdown                     #
# --------------------------------------------------------------------------- #

def _run_demo(kb_only: bool = True) -> int:
    """Pick a random KB case and run it through RAGE+Judge with full detail."""
    from rage_core.llm.openai_compat import get_judge_model, get_llm_model, llm_judge_enabled
    from rage_core.layers.layer4_decision import DefensePipeline
    from rage_core.models import ConversationState

    cases = load_dataset(include_kb=kb_only, include_scenarios=not kb_only)
    case = random.choice(cases)

    use_judge = llm_judge_enabled()
    judge_model = get_judge_model("nvidia/llama-3.1-nemotron-nano-8b-v1")

    W = 70
    print()
    print("=" * W)
    print("  RAGE + Juez — Demo de caso aleatorio")
    print("=" * W)
    print(f"  Caso       : {case.id}")
    print(f"  Categoría  : {case.category}")
    print(f"  Descripción: {case.description}")
    print(f"  Etiqueta KB: {'ATAQUE' if case.is_attack else 'BENIGNO'}")
    print()
    print(f"  Mensaje evaluado:")
    print(f"  > {case.text}")
    print("=" * W)

    pipeline = DefensePipeline(apply_session_ratchet=False)
    if not use_judge:
        pipeline._l3._use_llm = False  # noqa: SLF001

    state = ConversationState()
    print()
    print("  Evaluando con RAGE...", end=" ", flush=True)
    signal = pipeline.evaluate(case.text, state)
    print("listo.")
    print()
    print("─" * W)
    print("  RESULTADOS POR CAPA")
    print("─" * W)

    # L1
    l1 = signal.layer1
    l1_status = f"MATCH ({l1.pattern_id} — '{l1.matched_text}')" if l1.matched else "sin coincidencia"
    print(f"  L1  Firmas deterministas : {l1_status}")

    # L2
    l2 = signal.layer2
    if l2.score >= 0.25:
        print(f"  L2  Similitud KB         : {l2.score:.3f}  [{l2.top_match_category} / {l2.top_match_technique}]")
    else:
        print(f"  L2  Similitud KB         : {l2.score:.3f}  (baja — no coincide con ataques conocidos)")

    # L3
    l3 = signal.layer3
    drift_note = "alto — deriva semántica detectada" if l3.drift > 0.5 else "bajo"
    print(f"  L3  Drift semántico      : {l3.drift:.3f}  ({drift_note})")
    if use_judge:
        judge_note = "ATAQUE confirmado por juez" if l3.llm_flagged else "juez dice BENIGNO"
        print(f"  L3  Juez LLM ({judge_model.split('/')[-1][:20]}) : {judge_note}")
    else:
        print(f"  L3  Juez LLM             : DESACTIVADO (activa RAGE_USE_LLM_JUDGE=1)")

    # L4
    print(f"  L4  Score final          : {signal.score:.1f} / 100  →  banda [{signal.band.value.upper()}]")

    print("─" * W)

    # Verdict
    rage_verdict = l1.matched or (use_judge and l3.llm_flagged)
    verdict_str = "ATAQUE" if rage_verdict else "BENIGNO"
    kb_str = "ATAQUE" if case.is_attack else "BENIGNO"
    match = rage_verdict == case.is_attack
    outcome_str = "CORRECTO ✓" if match else "FALLO ✗"

    print()
    print(f"  KB dice       : {kb_str}")
    print(f"  RAGE+Juez dice: {verdict_str}")
    print(f"  Resultado     : {outcome_str}")

    if not match and not rage_verdict and case.is_attack:
        print()
        print("  NOTA: Este ataque no fue detectado por L1 ni por el juez.")
        if not use_judge:
            print("        Activa el juez con RAGE_USE_LLM_JUDGE=1 para mejor cobertura.")

    print("=" * W)
    return 0


_BENIGN_PREAMBLE_TEXT = "Can you show me the sales report for this quarter?"


def _run_all_demos(include_kb: bool = True, include_scenarios: bool = True) -> int:
    """Run every case from the dataset one by one with full layer breakdown.

    Press Enter to advance to the next case, or Ctrl+C to stop.
    Attack cases get a benign preamble turn so the LLM judge activates.
    """
    from rage_core.llm.openai_compat import get_judge_model, llm_judge_enabled
    from rage_core.layers.layer4_decision import DefensePipeline
    from rage_core.models import ConversationState

    cases = load_dataset(include_kb=include_kb, include_scenarios=include_scenarios)
    use_judge = llm_judge_enabled()
    judge_model = get_judge_model("nvidia/llama-3.1-nemotron-nano-8b-v1")

    W = 70
    correct = 0
    total = len(cases)

    print()
    print(f"  {total} casos en total  |  Juez: {'ACTIVO' if use_judge else 'DESACTIVADO'}")
    if use_judge:
        print(f"  Modelo juez: {judge_model}")
        print("  Ataques: evaluados con turno benigno previo para activar el juez")
    print("  Pulsa Enter para avanzar al siguiente caso, Ctrl+C para salir.")

    for idx, case in enumerate(cases, 1):
        try:
            input(f"\n  [Enter] → Caso {idx}/{total} ...")
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Interrumpido.")
            break

        # Fresh pipeline per case to avoid any state leakage
        pipeline = DefensePipeline(apply_session_ratchet=False)
        if not use_judge:
            pipeline._l3._use_llm = False  # noqa: SLF001

        state = ConversationState()
        preamble_used = False

        if use_judge and case.is_attack:
            # Warm-up benign turn → establishes embedding baseline → drift is
            # high on the attack turn → judge gets called
            pipeline.evaluate(_BENIGN_PREAMBLE_TEXT, state)
            preamble_used = True

        signal = pipeline.evaluate(case.text, state)
        l1, l2, l3, l4 = signal.layer1, signal.layer2, signal.layer3, signal

        rage_verdict = l1.matched or (use_judge and l3.llm_flagged)
        match = rage_verdict == case.is_attack
        if match:
            correct += 1

        print()
        print("=" * W)
        print(f"  Caso {idx}/{total}  —  {case.id}")
        print(f"  Categoría  : {case.category}")
        print(f"  Etiqueta KB: {'ATAQUE' if case.is_attack else 'BENIGNO'}")
        if preamble_used:
            print(f"  Contexto   : turno benigno previo añadido (activa juez)")
        print()
        print(f"  > {case.text[:200]}")
        print("─" * W)
        l1_status = f"MATCH ({l1.pattern_id} — '{l1.matched_text}')" if l1.matched else "sin coincidencia"
        print(f"  L1  Firmas     : {l1_status}")
        l2_note = f"{l2.score:.3f}  [{l2.top_match_category}]" if l2.score >= 0.25 else f"{l2.score:.3f}  (baja)"
        print(f"  L2  Similitud  : {l2_note}")
        drift_note = f"{l3.drift:.3f}  ({'alto — juez activado' if l3.drift > 0.5 else 'bajo'})"
        print(f"  L3  Drift      : {drift_note}")
        if use_judge:
            if l3.llm_flagged:
                judge_note = "ATAQUE confirmado por juez"
            elif preamble_used and l3.drift > 0.5:
                judge_note = "juez consultado → BENIGNO"
            elif preamble_used:
                judge_note = "drift bajo — juez no consultado"
            else:
                judge_note = "sin turno previo — juez no consultado"
            print(f"  L3  Juez       : {judge_note}")
        print(f"  L4  Score      : {l4.score:.1f}/100  banda [{l4.band.value.upper()}]")
        print("─" * W)
        kb_str = "ATAQUE" if case.is_attack else "BENIGNO"
        verdict_str = "ATAQUE" if rage_verdict else "BENIGNO"
        outcome_str = "CORRECTO ✓" if match else "FALLO ✗"
        print(f"  KB: {kb_str}  |  RAGE+Juez: {verdict_str}  |  {outcome_str}")
        print(f"  Aciertos hasta ahora: {correct}/{idx}")
        print("=" * W)

    print()
    print(f"  Sesión completada: {correct}/{total} casos correctos  ({correct/total*100:.1f}%)")
    return 0


def _run_holdout(
    *,
    use_judge: bool,
    verbose: bool,
    by_category: bool,
    filter_arg: str | None,
    rag_threshold: float | None = None,
    eval_set: str | None = None,
) -> int:
    """Open-world evaluation on holdout cases never seen in the training KB."""
    if rag_threshold is not None:
        import rage_core.layers.access_policy as policy

        policy.RAG_ATTACK_THRESHOLD = rag_threshold

    if eval_set:
        cases = load_eval_holdout_dataset(eval_set)
        title = f"Evaluación PRÁCTICA (eval-set={eval_set})"
    else:
        cases = load_holdout_dataset()
        title = "Evaluación ABIERTA (holdout)"
    summary = dataset_summary(cases)

    print()
    print("=" * (sum(_COL.values()) + len(_COL) * 3))
    print(f"  RAGE — {title}")
    print("  Casos NO incluidos en threats.json / benign.json (solo evaluación)")
    print(f"  Dataset: {summary['total']} casos  "
          f"({summary['attacks']} ataques / {summary['benign']} benignos)")
    print("  La KB se usa solo para detectar (L2 RAG) — las respuestas no están memorizadas.")
    from rage_core.layers.access_policy import RAG_ATTACK_THRESHOLD
    print(f"  Umbral L2 RAG: {RAG_ATTACK_THRESHOLD}")
    print(f"  Juez LLM: {'ACTIVO' if use_judge else 'DESACTIVADO'}")
    if use_judge:
        from rage_core.llm.openai_compat import get_judge_model, llm_judge_enabled
        judge_ready = llm_judge_enabled()
        model = get_judge_model("nvidia/llama-3.1-nemotron-nano-8b-v1")
        print(f"  Modelo juez: {model}  (configurado: {'SI' if judge_ready else 'NO'})")
    print("=" * (sum(_COL.values()) + len(_COL) * 3))
    print()

    print("Evaluando casos holdout...", end=" ", flush=True)
    results = run_benchmark(cases, use_judge=use_judge)
    print(f"OK ({len(results)} casos)")
    print()

    display = _filter_results(results, filter_arg)
    if verbose:
        display = results
    elif filter_arg is None:
        display = [r for r in results if not r.correct]

    if display:
        _print_header()
        for r in display:
            _print_row(r)
        if not verbose and filter_arg is None:
            print()
            print(f"  (mostrando {len(display)} errores — usa --verbose para ver todos)")

    metrics = compute_metrics(results)
    _print_metrics(metrics, use_judge)
    _print_holdout_failures(results)
    if by_category:
        _print_category_metrics(compute_category_metrics(results))

    error_rate = 1.0 - metrics.accuracy
    print()
    print(f"  Tasa de error real: {error_rate * 100:.1f}%  ({metrics.total - metrics.correct} de {metrics.total} casos)")
    return 0


def _print_scenario_summary(scenario_metrics: dict[str, dict], scenarios: list) -> None:
    print()
    print("  Resumen por escenario multi-turno:")
    print(f"  {'Escenario':<28} {'Turnos atk':>10}  {'Detectados':>10}  {'FP':>4}  {'OK':>4}")
    print("  " + "─" * 62)
    passed = 0
    for s in scenarios:
        m = scenario_metrics.get(s.id, {})
        ok = "✓" if m.get("passed") else "✗"
        if m.get("passed"):
            passed += 1
        print(
            f"  {s.id:<28} {m.get('attack_turns', 0):>10}  "
            f"{m.get('attack_detected', 0):>10}  {m.get('benign_fp', 0):>4}  {ok:>4}"
        )
    print("  " + "─" * 62)
    print(f"  Escenarios OK: {passed}/{len(scenarios)}")


def _run_multi_turn(
    *,
    use_judge: bool,
    verbose: bool,
    by_category: bool,
    filter_arg: str | None,
    eval_set: str | None = None,
) -> int:
    """Multi-turn open-world evaluation with accumulated conversation context."""
    if eval_set:
        scenarios = load_eval_scenarios(eval_set)
        title = f"Evaluación MULTI-TURNO PRÁCTICA (eval-set={eval_set})"
    else:
        scenarios = load_holdout_scenarios()
        title = "Evaluación MULTI-TURNO (holdout scenarios)"
    if not scenarios:
        print("ERROR: no hay escenarios multi-turno.", file=sys.stderr)
        return 1

    summary = scenario_summary(scenarios)
    print()
    print("=" * (sum(_COL.values()) + len(_COL) * 3))
    print(f"  RAGE — {title}")
    print("  Cada escenario corre en secuencia con contexto acumulado (Crescendo-style)")
    print(f"  Escenarios: {summary['scenarios']}  |  Turnos: {summary['turns']}  "
          f"({summary['attacks']} ataques / {summary['benign']} benignos)")
    print(f"  Juez LLM: {'ACTIVO' if use_judge else 'DESACTIVADO'}")
    print("=" * (sum(_COL.values()) + len(_COL) * 3))
    print()

    print("Evaluando escenarios...", end=" ", flush=True)
    results = run_multi_turn_benchmark(scenarios, use_judge=use_judge)
    print(f"OK ({len(results)} turnos)")
    print()

    display = _filter_results(results, filter_arg)
    if verbose:
        display = results
    elif filter_arg is None:
        display = [r for r in results if not r.correct]

    if display:
        _print_header()
        for r in display:
            _print_row(r)
        if not verbose and filter_arg is None and display:
            print()
            print(f"  (mostrando {len(display)} errores — usa --verbose para ver todos)")

    metrics = compute_metrics(results)
    _print_metrics(metrics, use_judge)
    _print_scenario_summary(compute_scenario_metrics(scenarios, results), scenarios)
    _print_holdout_failures(results)
    if by_category:
        _print_category_metrics(compute_category_metrics(results))

    error_rate = 1.0 - metrics.accuracy
    print()
    print(f"  Tasa de error (turnos): {error_rate * 100:.1f}%")
    return 0


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE+Judge benchmark — compara predicciones contra KB ground-truth"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Ejecuta un caso aleatorio de la KB con desglose completo por capa",
    )
    parser.add_argument(
        "--all-demos",
        action="store_true",
        dest="all_demos",
        help="Recorre todos los casos uno a uno con desglose completo (pulsa Enter para avanzar)",
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
        help="Usar solo la KB (threats.json + benign.json), sin escenarios",
    )
    parser.add_argument(
        "--attacks-kb-only",
        action="store_true",
        help="Usar solo threats.json (ataques KB, sin benignos ni escenarios)",
    )
    parser.add_argument(
        "--benign-kb-only",
        action="store_true",
        help="Usar solo benign.json (benignos KB, sin ataques ni escenarios)",
    )
    parser.add_argument(
        "--by-category",
        action="store_true",
        help="Mostrar métricas desglosadas por categoría",
    )
    parser.add_argument(
        "--holdout",
        action="store_true",
        help="Evaluación abierta: casos prácticos NO en la KB (base + investigación OWASP/Crescendo)",
    )
    parser.add_argument(
        "--rag-threshold",
        type=float,
        default=None,
        metavar="SCORE",
        help="Override L2 RAG threshold (default 0.75). Útil para experimentar en holdout.",
    )
    parser.add_argument(
        "--multi-turn",
        action="store_true",
        dest="multi_turn",
        help="Evaluación multi-turno: escenarios secuenciales con contexto acumulado (Crescendo)",
    )
    parser.add_argument(
        "--scenarios-only",
        action="store_true",
        help="Usar solo los turnos de los escenarios (no la KB)",
    )
    parser.add_argument(
        "--eval-set",
        metavar="NAME",
        default=None,
        help="Usar dataset de práctica alternativo (ej. practice). No cambia KB ni detección.",
    )
    parser.add_argument(
        "--filter",
        metavar="OUTCOME",
        choices=["tp", "tn", "fp", "fn", "TP", "TN", "FP", "FN"],
        help="Mostrar solo un tipo de resultado: tp / tn / fp / fn",
    )
    args = parser.parse_args()

    if args.multi_turn:
        return _run_multi_turn(
            use_judge=not args.no_judge,
            verbose=args.verbose,
            by_category=args.by_category,
            filter_arg=args.filter,
            eval_set=args.eval_set,
        )

    if args.holdout:
        return _run_holdout(
            use_judge=not args.no_judge,
            verbose=args.verbose,
            by_category=args.by_category,
            filter_arg=args.filter,
            rag_threshold=args.rag_threshold,
            eval_set=args.eval_set,
        )

    if args.demo:
        return _run_demo(kb_only=not args.scenarios_only)

    if args.all_demos:
        return _run_all_demos(
            include_kb=not args.scenarios_only,
            include_scenarios=not args.kb_only,
        )

    use_judge = not args.no_judge
    include_kb = not args.scenarios_only and not args.benign_kb_only
    include_benign_kb = not args.scenarios_only and not args.attacks_kb_only
    include_scenarios = (
        not args.kb_only and not args.attacks_kb_only and not args.benign_kb_only
    )

    # Load dataset
    cases = load_dataset(
        include_kb=include_kb,
        include_benign_kb=include_benign_kb,
        include_scenarios=include_scenarios,
    )
    if not cases:
        print("ERROR: dataset vacío.", file=sys.stderr)
        return 1

    summary = dataset_summary(cases)
    print()
    print("=" * (sum(_COL.values()) + len(_COL) * 3))
    print("  RAGE+Judge Benchmark")
    print(f"  Dataset: {summary['total']} casos  "
          f"({summary['attacks']} ataques / {summary['benign']} benignos)")
    if summary.get("categories"):
        cat_count = len(summary["categories"])
        print(f"  Categorías : {cat_count} familias distintas")
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
    if args.by_category:
        _print_category_metrics(compute_category_metrics(results))

    # Exit code
    return 0 if metrics.accuracy >= 0.80 else 1


def main_holdout() -> int:
    """Entry point for rage-bench-holdout — open-world evaluation only."""
    import sys

    if "--holdout" not in sys.argv:
        sys.argv.insert(1, "--holdout")
    return main()


def main_multi_turn() -> int:
    """Entry point for rage-bench-multi-turn — multi-turn scenario evaluation."""
    import sys

    if "--multi-turn" not in sys.argv:
        sys.argv.insert(1, "--multi-turn")
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
