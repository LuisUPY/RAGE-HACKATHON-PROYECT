"""Live chat-style rendering for benchmark runs."""
from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rage_core.benchmark.dataset import BenchmarkScenario
    from rage_core.benchmark.evaluator import CaseResult

_W = 68


def _flush() -> None:
    sys.stdout.flush()


def print_benchmark_banner(*, title: str, subtitle: str, judge_model: str) -> None:
    print()
    print("=" * (_W + 4))
    print(f"  {title}")
    print(f"  {subtitle}")
    print(f"  Juez LLM: ACTIVO  ·  {judge_model}")
    print("=" * (_W + 4))
    print("  Vista en vivo — cada mensaje como en el chat de soporte")
    print("=" * (_W + 4))
    _flush()


def print_scenario_header(
    scenario: BenchmarkScenario,
    *,
    scenario_index: int,
    scenario_total: int,
) -> None:
    print()
    print("╔" + "═" * (_W + 2) + "╗")
    print(f"║  ESCENARIO {scenario_index}/{scenario_total} · {scenario.id}")
    desc = f"{scenario.category} — {scenario.description}"
    if len(desc) > _W:
        desc = desc[: _W - 3] + "..."
    print(f"║  {desc}")
    print("╚" + "═" * (_W + 2) + "╝")
    _flush()


def print_turn_live(
    result: CaseResult,
    *,
    turn_index: int,
    turn_total: int,
    delay_sec: float = 0.0,
    scenario_id: str | None = None,
) -> None:
    """Render one benchmark turn like an interactive chat + RAGE verdict."""
    case = result.case
    sig = result.signal
    expected = "ATAQUE" if case.is_attack else "BENIGNO"
    verdict = "ATAQUE" if result.rage_verdict else "BENIGNO"
    ok_mark = "✓" if result.correct else "✗"

    if result.rage_verdict:
        action = "BLOQUEADO" if case.is_attack else "BLOQUEADO (falso positivo)"
        action_color = action
    else:
        action = "PERMITIDO" if not case.is_attack else "PERMITIDO (ataque pasó)"
        action_color = action

    prefix = f"[{scenario_id}] " if scenario_id and not case.id.startswith("mt:") else ""
    turn_label = f"Turno {turn_index + 1}/{turn_total}"
    expect_label = "ataque esperado" if case.is_attack else "benigno esperado"

    print()
    print(f"  {turn_label}  ({expect_label})")
    print("  ┌─ Usuario " + "─" * (_W - 10))
    for line in _wrap(case.text, _W - 4):
        print(f"  │ {line}")
    print("  └" + "─" * (_W + 2))

    l1 = sig.layer1.pattern_id if sig.layer1.matched else "—"
    judge = "SÍ" if sig.layer3.llm_flagged else "no"
    l2 = f"{sig.layer2.score:.2f}"
    drift = f"{sig.layer3.drift:.2f}"

    print("  ┌─ RAGE + Juez " + "─" * (_W - 14))
    print(f"  │ {ok_mark} {action_color}")
    print(f"  │ Veredicto: {verdict}  ·  KB: {expected}  ·  Resultado: {result.outcome}")
    print(
        f"  │ L1: {l1:<10}  L2: {l2}  Drift: {drift}  "
        f"Juez: {judge:<3}  Score: {sig.score:.0f} [{sig.band.value}]"
    )
    if sig.layer3.llm_flagged:
        print("  │ Juez LLM: confirmó escalada / inyección")
    elif sig.layer1.matched:
        print(f"  │ L1: firma {sig.layer1.matched_text!r}")
    print("  └" + "─" * (_W + 2))
    _flush()

    if delay_sec > 0:
        time.sleep(delay_sec)


def print_single_case_live(
    result: CaseResult,
    *,
    case_index: int,
    case_total: int,
    delay_sec: float = 0.0,
) -> None:
    print()
    print(f"  ── Caso {case_index}/{case_total}  ·  {result.case.id}  ·  {result.case.category} ──")
    print_turn_live(
        result,
        turn_index=0,
        turn_total=1,
        delay_sec=0.0,
    )
    if delay_sec > 0:
        time.sleep(delay_sec)


def _wrap(text: str, width: int) -> list[str]:
    text = text.replace("\n", " ").strip()
    if len(text) <= width:
        return [text]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text[:width]]
