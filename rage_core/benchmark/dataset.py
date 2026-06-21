"""
Benchmark dataset — labeled cases for RAGE+Judge evaluation.

Sources:
  1. KB (rage_core/kb/threats.json) — 33 known attack patterns, all is_attack=True.
  2. Attack scenarios (rage_core/demo/attacks.py) — multi-turn scenarios with
     per-turn is_attack labels (includes both attack and benign turns).

The KB entries are single-turn "probe" texts — the ground truth is that each one
is a known injection/attack pattern documented by the security team.

The scenario turns capture the realistic multi-turn structure of attacks like
Crescendo escalation, giving the benchmark both isolated patterns and context.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_KB_PATH = Path(__file__).parent.parent / "kb" / "threats.json"


@dataclass
class BenchmarkCase:
    """A single labeled case for evaluation."""

    id: str
    text: str
    is_attack: bool    # ground truth: True = known attack, False = benign
    source: str        # "kb" | "scenario:<scenario_name>"
    category: str      # attack category (e.g. "override_direct") or "benign"
    description: str   # human-readable annotation


def _load_kb_cases() -> list[BenchmarkCase]:
    """Load all entries from threats.json — all are labeled is_attack=True."""
    with open(_KB_PATH, encoding="utf-8") as fh:
        entries = json.load(fh)

    cases: list[BenchmarkCase] = []
    for entry in entries:
        cases.append(BenchmarkCase(
            id=f"kb:{entry['id']}",
            text=entry["text"],
            is_attack=True,
            source="kb",
            category=entry["category"],
            description=entry["technique"],
        ))
    return cases


def _load_scenario_cases() -> list[BenchmarkCase]:
    """Load per-turn cases from ALL_SCENARIOS in attacks.py."""
    from rage_core.demo.attacks import ALL_SCENARIOS

    cases: list[BenchmarkCase] = []
    for scenario_name, turns in ALL_SCENARIOS.items():
        for idx, turn in enumerate(turns):
            cases.append(BenchmarkCase(
                id=f"scenario:{scenario_name}:t{idx}",
                text=turn.user_text,
                is_attack=turn.is_attack,
                source=f"scenario:{scenario_name}",
                category=scenario_name if turn.is_attack else "benign",
                description=turn.description or f"Turn {idx} of {scenario_name}",
            ))
    return cases


def load_dataset(
    include_kb: bool = True,
    include_scenarios: bool = True,
) -> list[BenchmarkCase]:
    """Return the full labeled benchmark dataset.

    Args:
        include_kb: Include all 33 KB entries (all attacks).
        include_scenarios: Include turns from ALL_SCENARIOS (mix of attacks + benign).

    Returns:
        List of BenchmarkCase with ground-truth is_attack labels.
    """
    cases: list[BenchmarkCase] = []
    if include_kb:
        cases.extend(_load_kb_cases())
    if include_scenarios:
        cases.extend(_load_scenario_cases())
    return cases


def dataset_summary(cases: list[BenchmarkCase]) -> dict:
    """Return a simple summary dict for display purposes."""
    attacks = sum(1 for c in cases if c.is_attack)
    benign = len(cases) - attacks
    sources = {}
    for c in cases:
        sources[c.source] = sources.get(c.source, 0) + 1
    return {
        "total": len(cases),
        "attacks": attacks,
        "benign": benign,
        "sources": sources,
    }
