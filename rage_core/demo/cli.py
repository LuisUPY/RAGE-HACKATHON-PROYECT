"""
RAGE product demo — multi-turn scenarios with LLM judge (user API keys).

Usage:
    uv run rage-demo                          # todos los casos + juez (pide API key)
    uv run rage-demo --core                   # 14 escenarios multi-turno
    uv run rage-demo --offline --no-plot      # sin juez (CI / rápido)
    uv run rage-demo --list
    uv run rage-demo --support                # chat soporte IT
"""
from __future__ import annotations

import argparse
import sys

from rage_core.demo.demo_scenarios import ALL_DEMO_SCENARIOS, CORE_DEMO_SCENARIOS
from rage_core.demo.orchestrator import ScenarioOrchestrator
from rage_core.metrics.auc_degradation import compute_auc, plot_auc_curves, print_auc_report


def _print_turn(record, *, defended: bool, show_judge: bool) -> None:
    tag = "ATAQUE" if record.is_attack else "benigno"
    block = "BLOQUEADO" if record.blocked else "permitido"
    print(f"\n  T{record.turn_index} [{tag}] {block}")
    print(f"    > {record.user_text[:90]}{'...' if len(record.user_text) > 90 else ''}")
    if defended and record.signal is not None:
        sig = record.signal
        l1 = sig.layer1.pattern_id if sig.layer1.matched else "—"
        j = "SÍ" if record.judge_flagged else "no"
        parts = [
            f"L1={l1}",
            f"L2={sig.layer2.score:.2f}",
            f"score={sig.score:.0f}",
            f"band={sig.band.value}",
        ]
        if show_judge:
            parts.append(f"juez={j}")
        parts.append(f"gt={record.gt_score}")
        print(f"    {'  '.join(parts)}")
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
    from rage_core.llm.openai_compat import get_judge_model

    orchestrator = ScenarioOrchestrator(use_judge=use_judge, apply_ratchet=True)
    auc_results: list = []
    total_turns = 0
    judge_blocks = 0

    print()
    print("=" * 62)
    if use_judge:
        print("  RAGE DEMO — juez LLM ACTIVO")
        print(f"  Modelo juez: {get_judge_model('nvidia/llama-3.1-nemotron-nano-8b-v1')}")
    else:
        print("  RAGE DEMO — modo offline (sin juez)")
    print(f"  Escenarios: {len(names)}")
    print("=" * 62)

    for name in names:
        turns = ALL_DEMO_SCENARIOS.get(name)
        if turns is None:
            print(f"  Escenario desconocido: {name}", file=sys.stderr)
            return 1

        total_turns += len(turns) * 2

        print(f"\n{'─' * 62}")
        print(f"  [{names.index(name) + 1}/{len(names)}] {name}  ({len(turns)} turnos)")
        print(f"{'─' * 62}")

        undefended = orchestrator.run(name, turns, defended=False)
        defended = orchestrator.run(name, turns, defended=True)

        if use_judge:
            judge_blocks += sum(
                1 for r in defended.records if r.blocked and r.judge_flagged
            )

        if verbose:
            print("\n  --- Sin defensa ---")
            for rec in undefended.records:
                _print_turn(rec, defended=False, show_judge=False)
            print("\n  --- Con RAGE + Juez ---" if use_judge else "\n  --- Con RAGE ---")
            for rec in defended.records:
                _print_turn(rec, defended=True, show_judge=use_judge)

        auc_results.append(compute_auc(undefended.mode_label, undefended.gt_scores))
        auc_results.append(compute_auc(defended.mode_label, defended.gt_scores))

        u_comp = next((i for i, s in enumerate(undefended.gt_scores) if s >= 4), None)
        d_comp = next((i for i, s in enumerate(defended.gt_scores) if s >= 4), None)
        atk = sum(1 for t in turns if t.is_attack)
        det = sum(1 for r in defended.records if r.is_attack and r.blocked)
        print(
            f"  AUC sin defensa: {auc_results[-2].auc_normalized:.3f}  "
            f"compromiso T{u_comp if u_comp is not None else '—'}"
        )
        print(
            f"  AUC con RAGE   : {auc_results[-1].auc_normalized:.3f}  "
            f"compromiso T{d_comp if d_comp is not None else '—'}  "
            f"detección {det}/{atk} ataques"
        )

    print_auc_report(auc_results)

    if not no_plot and auc_results:
        show = sys.stdout.isatty()
        plot_auc_curves(auc_results, output_path=output, show=show)
        if output:
            print(f"  Gráfica guardada en {output}")

    print()
    print(f"  Escenarios ejecutados : {len(names)}")
    print(f"  Turnos evaluados      : {total_turns}")
    if use_judge:
        print(f"  Bloqueos por juez LLM : {judge_blocks}")
    print("  Demo completada.")
    return 0


def _run_support_chat(argv: list[str]) -> int:
    from rage_core.demo.support_chat_cli import main as support_main

    sys.argv = ["rage-chat-support", *argv]
    return support_main()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAGE demo — escenarios defended vs baseline + juez LLM",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        metavar="NAME",
        help="Escenario concreto (repetible)",
    )
    parser.add_argument("--list", action="store_true", help="Listar escenarios disponibles")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Todos los escenarios incl. probes single-turn (default)",
    )
    parser.add_argument(
        "--core",
        action="store_true",
        help="Solo escenarios multi-turno principales (14)",
    )
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
        help="Abrir chat de soporte IT interactivo",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Sin juez LLM ni API key (solo L1+L2, modo rápido)",
    )
    args, rest = parser.parse_known_args()

    if args.list:
        print(f"Escenarios demo ({len(ALL_DEMO_SCENARIOS)} total):\n")
        print("  Multi-turno core:")
        for name in ALL_DEMO_SCENARIOS:
            if name.startswith("probe_"):
                continue
            n = len(ALL_DEMO_SCENARIOS[name])
            core = " *" if name in CORE_DEMO_SCENARIOS else ""
            print(f"    {name:<32} {n:>2} turnos{core}")
        print("\n  Single-turn probes:")
        for name in sorted(k for k in ALL_DEMO_SCENARIOS if k.startswith("probe_")):
            print(f"    {name}")
        return 0

    if args.support:
        return _run_support_chat(rest)

    use_judge = not args.offline
    if use_judge:
        from rage_core.demo.bootstrap import ensure_llm_ready

        print("\nDemo con juez LLM — introduce tu API key (solo esta sesión).\n")
        ok, msg = ensure_llm_ready(
            interactive=True,
            verify=True,
            require_judge=True,
            force_prompt=True,
        )
        if not ok:
            print(msg, file=sys.stderr)
            return 1
        print(f"✓ {msg}\n")

    if args.core:
        names = list(CORE_DEMO_SCENARIOS)
    elif args.scenarios:
        names = args.scenarios
    elif args.all or not args.offline:
        names = list(ALL_DEMO_SCENARIOS.keys())
    else:
        names = list(CORE_DEMO_SCENARIOS)

    return _run_scenarios(
        names,
        use_judge=use_judge,
        verbose=args.verbose,
        no_plot=args.no_plot,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
