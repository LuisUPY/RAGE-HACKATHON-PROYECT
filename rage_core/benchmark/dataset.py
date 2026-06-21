"""
Benchmark dataset — labeled cases for RAGE+Judge evaluation.

Sources:
  1. KB attacks (rage_core/kb/threats.json) — known attack patterns, is_attack=True.
  2. KB benign (rage_core/kb/benign.json) — legitimate business queries, is_attack=False.
  3. Attack scenarios (rage_core/demo/attacks.py) — multi-turn scenarios with
     per-turn is_attack labels (includes both attack and benign turns).

The KB entries are single-turn probe texts with ground-truth labels.
Scenario turns capture realistic multi-turn structure (Crescendo, tool chains, etc.).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_KB_ATTACKS_PATH = Path(__file__).parent.parent / "kb" / "threats.json"
_KB_BENIGN_PATH = Path(__file__).parent.parent / "kb" / "benign.json"


@dataclass
class BenchmarkCase:
    """A single labeled case for evaluation."""

    id: str
    text: str
    is_attack: bool    # ground truth: True = known attack, False = benign
    source: str        # "kb" | "kb:benign" | "scenario:<scenario_name>"
    category: str      # attack category (e.g. "override_direct") or "benign"
    description: str   # human-readable annotation


def _load_kb_attack_cases() -> list[BenchmarkCase]:
    """Load all entries from threats.json — all are labeled is_attack=True."""
    with open(_KB_ATTACKS_PATH, encoding="utf-8") as fh:
        entries = json.load(fh)

    return [
        BenchmarkCase(
            id=f"kb:{entry['id']}",
            text=entry["text"],
            is_attack=True,
            source="kb",
            category=entry["category"],
            description=entry["technique"],
        )
        for entry in entries
    ]


def _load_kb_benign_cases() -> list[BenchmarkCase]:
    """Load labeled benign probes from benign.json."""
    with open(_KB_BENIGN_PATH, encoding="utf-8") as fh:
        entries = json.load(fh)

    return [
        BenchmarkCase(
            id=f"benign:{entry['id']}",
            text=entry["text"],
            is_attack=False,
            source="kb:benign",
            category=entry["category"],
            description=entry["context"],
        )
        for entry in entries
    ]


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
    include_benign_kb: bool = True,
    include_scenarios: bool = True,
) -> list[BenchmarkCase]:
    """Return the full labeled benchmark dataset.

    Args:
        include_kb: Include attack entries from threats.json.
        include_benign_kb: Include benign entries from benign.json.
        include_scenarios: Include turns from ALL_SCENARIOS (mix of attacks + benign).

    Returns:
        List of BenchmarkCase with ground-truth is_attack labels.
    """
    cases: list[BenchmarkCase] = []
    if include_kb:
        cases.extend(_load_kb_attack_cases())
    if include_benign_kb:
        cases.extend(_load_kb_benign_cases())
    if include_scenarios:
        cases.extend(_load_scenario_cases())
    return cases


def dataset_summary(cases: list[BenchmarkCase]) -> dict:
    """Return a simple summary dict for display purposes."""
    attacks = sum(1 for c in cases if c.is_attack)
    benign = len(cases) - attacks
    sources: dict[str, int] = {}
    categories: dict[str, int] = {}
    for c in cases:
        sources[c.source] = sources.get(c.source, 0) + 1
        categories[c.category] = categories.get(c.category, 0) + 1
    return {
        "total": len(cases),
        "attacks": attacks,
        "benign": benign,
        "sources": sources,
        "categories": categories,
    }
