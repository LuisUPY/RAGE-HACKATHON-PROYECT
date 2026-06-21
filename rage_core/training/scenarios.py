"""
Scenario loading for Training-Center.

Bridges rage_core.demo.attacks (built-in) with optional JSON scenario packs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rage_core.demo.attacks import ALL_SCENARIOS, Turn
from rage_core.training.paths import get_training_center_root


@dataclass
class ScenarioPack:
    id: str
    name: str
    description: str
    turns: list[Turn]
    category: str = "crescendo"
    tags: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "turn_count": len(self.turns),
            "category": self.category,
            "tags": self.tags or [],
        }


def _scenarios_dir() -> Path:
    return get_training_center_root() / "scenarios"


def _turn_from_json(raw: dict) -> Turn:
    return Turn(
        user_text=raw["user_text"],
        tool_name=raw.get("tool_name"),
        tool_args=raw.get("tool_args"),
        is_attack=raw.get("is_attack", False),
        description=raw.get("description", ""),
    )


def load_json_scenario(path: Path) -> ScenarioPack:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return ScenarioPack(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        turns=[_turn_from_json(t) for t in data["turns"]],
        category=data.get("category", "custom"),
        tags=data.get("tags"),
    )


def load_all_scenarios(scenario_ids: list[str] | None = None) -> list[ScenarioPack]:
    """Load built-in rage_core scenarios plus optional JSON packs."""
    packs: list[ScenarioPack] = []

    builtin_meta = {
        "drop_table_escalation": (
            "Gradual escalation → DROP TABLE",
            "Multi-turn role-change then destructive SQL",
        ),
        "canary_leak": (
            "Canary exfiltration",
            "Indirect injection to leak system canary token",
        ),
        "benign_conversation": (
            "Benign baseline",
            "Legitimate queries — measures false-positive rate",
        ),
        "crescendo_escalation": (
            "Crescendo UNION ALL exfiltration",
            "Benign escalation per arXiv:2404.01833 — tests cumulative drift + gateway",
        ),
    }

    for sid, turns in ALL_SCENARIOS.items():
        if scenario_ids and sid not in scenario_ids:
            continue
        name, desc = builtin_meta.get(sid, (sid, ""))
        packs.append(
            ScenarioPack(
                id=sid,
                name=name,
                description=desc,
                turns=turns,
                category="builtin",
                tags=["rage_core", sid],
            )
        )

    scenarios_dir = _scenarios_dir()
    if scenarios_dir.exists():
        for path in sorted(scenarios_dir.glob("*.json")):
            pack = load_json_scenario(path)
            if scenario_ids is None or pack.id in scenario_ids:
                if not any(p.id == pack.id for p in packs):
                    packs.append(pack)

    return packs
