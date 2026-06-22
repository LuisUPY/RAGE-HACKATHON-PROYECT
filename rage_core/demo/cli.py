"""
RAGE product demo — offline scenario runner with AUC degradation report.

Usage:
    uv run rage-demo                          # all scenarios, offline
    uv run rage-demo --scenario drop_table_escalation
    uv run rage-demo --no-plot
    uv run rage-demo --list
    uv run rage-demo --support                # interactive IT support chat
"""
from __future__ import annotations

import argparse
import sys

from rage_core.demo.attacks import ALL_SCENARIOS
from rage_core.demo.orchestrator import ScenarioOrchestrator
from rage_core.metrics.auc_degradation import compute_auc, plot_auc_curves, print_auc_report


_DEFAULT_SCENARIOS = (
    "drop_table_escalation",
    "canary_leak",
    "benign_conversation",
)


def _print_turn(record, *, defended: bool) -> None:
    tag = "ATAQUE" if record.is_attack else "benigno"
    block = "BLOQUEADO" if record.blocked else "permitido"
    print(f"\n  T{record.turn_index} [{tag}] {block}")
    print(f"    > {record.user_text[:90]}{'...' if len(record.user_text) > 90 else ''}")
    if defended and record.signal is not None:
        sig = record.signal
        l1 = sig.layer1.pattern_id if sig.layer1.matched else "—"
        print(
            f"    L1={l1}  L2={sig.layer2.score:.2f}  "
            f"score={sig.score:.0f}  band={sig.band.value}  gt={record.gt_score}"
        )
    else:
        print(f"    gt={record.gt_score}  resp={record.model_response[:60]}...")


def _run_scenarios(
    names: list[str],
    *,
    use_judge: bool,
    verbose: bool,
    no_plot: bool,
    output: str,
) -> int:
    orchestrator = ScenarioOrchestrator(use_judge=use_judge, apply_ratchet=True)
    auc_results = []

    print()
    print("=" * 62)
    print("  RAGE DEMO — escenarios multi-turno (offline, sin API key)")
    print("=" * 62)

    for name in names:
        turns = ALL_SCENARIOS.get(name)
        if turns is None:
            print(f"  Escenario desconocido: {name}", file=sys.stderr)
            return 1

        print(f"\n{'─' * 62}")
        print(f"  Escenario: {name}  ({len(turns)} turnos)")
        print(f"{'─' * 62}")

        undefended = orchestrator.run(name, turns, defended=False)
        defended = orchestrator.run(name, turns, defended=True)

        if verbose:
            print("\n  --- Sin defensa ---")
            for rec in undefended.records:
                _print_turn(rec, defended=False)
            print("\n  --- Con RAGE ---")
            for rec in defended.records:
                _print_turn(rec, defended=True)

        auc_results.append(compute_auc(undefended.mode_label, undefended.gt_scores))
        auc_results.append(compute_auc(defended.mode_label, defended.gt_scores))

        u_comp = next((i for i, s in enumerate(undefended.gt_scores) if s >= 4), None)
        d_comp = next((i for i, s in enumerate(defended.gt_scores) if s >= 4), None)
        print(f"  AUC sin defensa : {auc_results[-2].auc_normalized:.3f}  compromiso T{u_comp if u_comp is not None else '—'}")
        print(f"  AUC con RAGE    : {auc_results[-1].auc_normalized:.3f}  compromiso T{d_comp if d_comp is not None else '—'}")

    print_auc_report(auc_results)

    if not no_plot:
        show = sys.stdout.isatty()
        plot_auc_curves(auc_results, output_path=output, show=show)
        if output:
            print(f"  Gráfica guardada en {output}")

    print("  Demo completada.")
    return 0


def _run_support_chat(argv: list[str]) -> int:
    from rage_core.demo.support_chat_cli import main as support_main

    sys.argv = ["rage-chat-support", *argv]
    return support_main()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE product demo — escenarios defended vs baseline + AUC report",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        metavar="NAME",
        help="Escenario a ejecutar (repetible). Default: 3 escenarios principales.",
    )
    parser.add_argument("--list", action="store_true", help="Listar escenarios disponibles")
    parser.add_argument("--all", action="store_true", help="Ejecutar los 6 escenarios")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mostrar cada turno")
    parser.add_argument("--no-plot", action="store_true", help="No generar gráfica AUC")
    parser.add_argument(
        "--output",
        default="auc_results.png",
        help="Ruta PNG para la gráfica (default: auc_results.png)",
    )
    parser.add_argument(
        "--support",
        action="store_true",
        help="Abrir chat de soporte IT interactivo (requiere API key)",
    )
    parser.add_argument(
        "--with-judge",
        action="store_true",
        help="Activar juez LLM en el orquestador (requiere API key)",
    )
    args, rest = parser.parse_known_args()

    if args.list:
        print("Escenarios disponibles:")
        for name in ALL_SCENARIOS:
            n = len(ALL_SCENARIOS[name])
            print(f"  {name:<28} {n} turnos")
        return 0

    if args.support:
        return _run_support_chat(rest)

    if args.with_judge:
        from rage_core.demo.bootstrap import ensure_llm_ready

        ok, msg = ensure_llm_ready(interactive=True, verify=True, require_judge=True)
        if not ok:
            print(msg, file=sys.stderr)
            return 1

    if args.all:
        names = list(ALL_SCENARIOS.keys())
    elif args.scenarios:
        names = args.scenarios
    else:
        names = list(_DEFAULT_SCENARIOS)

    return _run_scenarios(
        names,
        use_judge=args.with_judge,
        verbose=args.verbose,
        no_plot=args.no_plot,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
