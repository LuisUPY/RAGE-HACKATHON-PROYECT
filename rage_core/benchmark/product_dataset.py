"""Product benchmark dataset — eval_product with profile tags."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rage_core.benchmark.dataset import ScenarioTurn, _kb_text_index

_EVAL_PRODUCT_DIR = Path(__file__).parent.parent / "kb" / "eval_product"


@dataclass
class ProductCase:
    """Single-turn product benchmark case."""

    id: str
    text: str
    is_attack: bool
    profile_id: str
    category: str
    description: str
    source: str = "eval:product"


@dataclass
class ProductScenario:
    """Multi-turn product benchmark scenario."""

    id: str
    profile_id: str
    category: str
    description: str
    turns: list[ScenarioTurn]
    source: str = "eval:product"


def _holdout_path() -> Path:
    return _EVAL_PRODUCT_DIR / "holdout.json"


def _scenarios_path() -> Path:
    return _EVAL_PRODUCT_DIR / "scenarios.json"


def load_product_holdout(*, default_profile: str = "practice") -> list[ProductCase]:
    path = _holdout_path()
    if not path.is_file():
        raise FileNotFoundError(f"Missing product holdout: {path}")
    kb_texts = _kb_text_index()
    entries = json.loads(path.read_text(encoding="utf-8"))
    cases: list[ProductCase] = []
    for entry in entries:
        normalized = entry["text"].lower().strip()
        if normalized in kb_texts:
            raise ValueError(f"Product case {entry['id']!r} duplicates KB text")
        cases.append(
            ProductCase(
                id=entry["id"],
                text=entry["text"],
                is_attack=entry["is_attack"],
                profile_id=entry.get("profile", default_profile),
                category=entry.get("category", "unknown"),
                description=entry.get("description", ""),
            )
        )
    return cases


def load_product_scenarios(*, default_profile: str = "practice") -> list[ProductScenario]:
    path = _scenarios_path()
    if not path.is_file():
        raise FileNotFoundError(f"Missing product scenarios: {path}")
    kb_texts = _kb_text_index()
    entries = json.loads(path.read_text(encoding="utf-8"))
    scenarios: list[ProductScenario] = []
    for entry in entries:
        turns: list[ScenarioTurn] = []
        for turn in entry["turns"]:
            normalized = turn["text"].lower().strip()
            if normalized in kb_texts:
                raise ValueError(f"Scenario {entry['id']!r} turn duplicates KB text")
            turns.append(
                ScenarioTurn(
                    text=turn["text"],
                    is_attack=turn["is_attack"],
                    description=turn.get("description", ""),
                )
            )
        scenarios.append(
            ProductScenario(
                id=entry["id"],
                profile_id=entry.get("profile", default_profile),
                category=entry.get("category", "unknown"),
                description=entry.get("description", ""),
                turns=turns,
            )
        )
    return scenarios


def count_product_turns(
    cases: list[ProductCase] | None = None,
    scenarios: list[ProductScenario] | None = None,
) -> int:
    cases = cases if cases is not None else load_product_holdout()
    scenarios = scenarios if scenarios is not None else load_product_scenarios()
    return len(cases) + sum(len(s.turns) for s in scenarios)
