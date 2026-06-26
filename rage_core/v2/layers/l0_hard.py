"""L0 — high-precision hard signals (≤25 rules)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from rage_core.v2.models import L0Signal

_RULES_PATH = Path(__file__).parent.parent / "kb" / "rules" / "l0_hard.json"


class HardSignals:
  """Deterministic patterns for unequivocal jailbreak / exfil / destructive SQL."""

  def __init__(self) -> None:
    raw = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    self._rules: list[tuple[str, str, re.Pattern[str]]] = []
    for entry in raw:
      self._rules.append(
        (entry["id"], entry["family"], re.compile(entry["pattern"], re.IGNORECASE))
      )

  def evaluate(self, text: str) -> L0Signal:
    best: L0Signal | None = None
    priority = {"sql_destructive": 3, "exfil": 2, "jailbreak": 1}
    best_rank = 0
    for rule_id, family, pattern in self._rules:
      if not pattern.search(text):
        continue
      rank = priority.get(family, 0)
      if rank >= best_rank:
        best_rank = rank
        best = L0Signal(hard_hit=True, rule_id=rule_id, family=family)
    return best or L0Signal()
