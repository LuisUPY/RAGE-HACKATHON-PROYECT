"""
Benchmark dataset — labeled cases for RAGE+Judge evaluation.

Sources:
  1. KB attacks (rage_core/kb/threats.json) — known attack patterns, is_attack=True.
  2. KB benign (rage_core/kb/benign.json) — legitimate business queries, is_attack=False.
  3. Holdout base (rage_core/kb/holdout.json) — practical paraphrases, not in KB.
  4. Holdout research (rage_core/kb/holdout_research.json) — OWASP LLM01:2025,
     AITG-APP-01, Crescendo (arXiv:2404.01833), and agent-tool abuse cases.
  5. Attack scenarios (rage_core/demo/attacks.py) — multi-turn scenarios.
  6. Holdout scenarios (holdout_scenarios.json + holdout_scenarios_extended.json)
     — open-world multi-turn (Crescendo, salami slicing, skeleton key, etc.).

The KB entries are single-turn probe texts with ground-truth labels.
Scenario turns capture realistic multi-turn structure (Crescendo, tool chains, etc.).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_KB_ATTACKS_PATH = Path(__file__).parent.parent / "kb" / "threats.json"
_KB_BENIGN_PATH = Path(__file__).parent.parent / "kb" / "benign.json"
_HOLDOUT_PATH = Path(__file__).parent.parent / "kb" / "holdout.json"
_HOLDOUT_RESEARCH_PATH = Path(__file__).parent.parent / "kb" / "holdout_research.json"
_HOLDOUT_SCENARIOS_PATH = Path(__file__).parent.parent / "kb" / "holdout_scenarios.json"
_HOLDOUT_SCENARIOS_EXTENDED_PATH = (
    Path(__file__).parent.parent / "kb" / "holdout_scenarios_extended.json"
)


@dataclass
class ScenarioTurn:
    """One turn in a multi-turn benchmark scenario."""

    text: str
    is_attack: bool
    description: str = ""


@dataclass
class BenchmarkScenario:
    """A labeled multi-turn conversation for sequential evaluation."""

    id: str
    category: str
    description: str
    turns: list[ScenarioTurn]
    source: str = "holdout:scenario"
    research_source: str = ""


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


def _kb_text_index() -> set[str]:
    """Normalized texts from the training KB (attacks + benign). Holdout must not overlap."""
    texts: set[str] = set()
    for path in (_KB_ATTACKS_PATH, _KB_BENIGN_PATH):
        with open(path, encoding="utf-8") as fh:
            for entry in json.load(fh):
                texts.add(entry["text"].lower().strip())
    return texts


def _load_holdout_cases() -> list[BenchmarkCase]:
    """Load holdout evaluation cases — never included in threats.json / benign.json."""
    kb_texts = _kb_text_index()
    cases: list[BenchmarkCase] = []

    for path in (_HOLDOUT_PATH, _HOLDOUT_RESEARCH_PATH):
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            entries = json.load(fh)

        for entry in entries:
            normalized = entry["text"].lower().strip()
            if normalized in kb_texts:
                raise ValueError(
                    f"Holdout case {entry['id']!r} duplicates KB text — "
                    "holdout must use novel wording not present in threats.json/benign.json"
                )
            desc = entry.get("description", entry.get("technique", ""))
            if entry.get("research_source"):
                desc = f"{desc} [{entry['research_source']}]"
            cases.append(BenchmarkCase(
                id=f"holdout:{entry['id']}",
                text=entry["text"],
                is_attack=entry["is_attack"],
                source="holdout",
                category=entry.get("category", entry.get("family", "unknown")),
                description=desc,
            ))
    return cases


def load_holdout_dataset() -> list[BenchmarkCase]:
    """Return practical holdout cases for open-world generalization evaluation."""
    return _load_holdout_cases()


def _parse_holdout_scenario_entries(
    entries: list[dict],
    kb_texts: set[str],
) -> list[BenchmarkScenario]:
    scenarios: list[BenchmarkScenario] = []
    for entry in entries:
        turns: list[ScenarioTurn] = []
        for t in entry["turns"]:
            normalized = t["text"].lower().strip()
            if normalized in kb_texts:
                raise ValueError(
                    f"Scenario {entry['id']!r} turn duplicates KB text"
                )
            turns.append(ScenarioTurn(
                text=t["text"],
                is_attack=t["is_attack"],
                description=t.get("description", ""),
            ))
        scenarios.append(BenchmarkScenario(
            id=entry["id"],
            category=entry.get("category", "unknown"),
            description=entry.get("description", ""),
            turns=turns,
            source="holdout:scenario",
            research_source=entry.get("research_source", ""),
        ))
    return scenarios


def _load_holdout_scenarios() -> list[BenchmarkScenario]:
    """Load multi-turn holdout scenarios from base + extended JSON files."""
    paths = [_HOLDOUT_SCENARIOS_PATH, _HOLDOUT_SCENARIOS_EXTENDED_PATH]
    if not any(p.exists() for p in paths):
        return []

    kb_texts = _kb_text_index()
    scenarios: list[BenchmarkScenario] = []
    seen_ids: set[str] = set()

    for path in paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            entries = json.load(fh)
        for entry in entries:
            if entry["id"] in seen_ids:
                raise ValueError(f"Duplicate holdout scenario id: {entry['id']!r}")
            seen_ids.add(entry["id"])
        scenarios.extend(_parse_holdout_scenario_entries(entries, kb_texts))

    return scenarios


def load_holdout_scenarios() -> list[BenchmarkScenario]:
    """Return open-world multi-turn scenarios for sequential evaluation."""
    return _load_holdout_scenarios()


def scenarios_to_cases(scenarios: list[BenchmarkScenario]) -> list[BenchmarkCase]:
    """Flatten scenarios into per-turn BenchmarkCase rows (for display)."""
    cases: list[BenchmarkCase] = []
    for scenario in scenarios:
        for idx, turn in enumerate(scenario.turns):
            desc = turn.description or f"Turn {idx} of {scenario.id}"
            if scenario.research_source:
                desc = f"{desc} [{scenario.research_source}]"
            cases.append(BenchmarkCase(
                id=f"mt:{scenario.id}:t{idx}",
                text=turn.text,
                is_attack=turn.is_attack,
                source=scenario.source,
                category=scenario.category if turn.is_attack else "benign",
                description=desc,
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


def scenario_summary(scenarios: list[BenchmarkScenario]) -> dict:
    """Summary for multi-turn scenario sets."""
    turn_total = sum(len(s.turns) for s in scenarios)
    attack_turns = sum(1 for s in scenarios for t in s.turns if t.is_attack)
    return {
        "scenarios": len(scenarios),
        "turns": turn_total,
        "attacks": attack_turns,
        "benign": turn_total - attack_turns,
        "categories": {s.category: sum(1 for _ in [s]) for s in scenarios},
    }
