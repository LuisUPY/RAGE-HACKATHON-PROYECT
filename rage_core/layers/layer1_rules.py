"""
Layer 1 — Deterministic pre-filter (regex / signature matching).

Cost: O(1) per turn, no ML, no API calls.
Exit early if a hard-coded pattern fires — cheapest possible defence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rage_core.models import Layer1Signal


@dataclass
class _Rule:
    rule_id: str
    description: str
    pattern: re.Pattern[str]


# Each entry: (rule_id, description, regex_pattern)
_RAW_RULES: list[tuple[str, str, str]] = [
    ("L1-001", "Explicit ignore-previous-instructions", r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?"),
    ("L1-002", "Explicit disregard system prompt", r"disregard\s+(your\s+)?(system\s+prompt|instructions?|guidelines?)"),
    ("L1-003", "Forget all / start fresh", r"forget\s+(everything|all|your)\s*(you\s+were\s+told|instructions?|rules?|guidelines?)?"),  # noqa: E501
    ("L1-004", "DAN / developer mode activation", r"\b(DAN|developer\s+mode|jailbreak\s+mode|unrestricted\s+mode)\b"),
    ("L1-005", "Override safety / bypass restrictions", r"(override|bypass|disable|remove)\s+(all\s+)?(safety|content|ethical)\s+(filters?|guidelines?|restrictions?|protocols?)"),  # noqa: E501
    ("L1-006", "SQL DROP TABLE attempt", r"\bDROP\s+TABLE\b"),
    ("L1-007", "SQL GRANT PRIVILEGES", r"\bGRANT\s+ALL\s+PRIVILEGES\b"),
    ("L1-008", "Base64 decode-and-execute instruction", r"(decode\s+and\s+execute|run\s+this\s+decoded)"),
    ("L1-009", "Explicit new system instruction injection", r"\[?\s*(SYSTEM|INJECTED?\s+INSTRUCTION|NEW\s+INSTRUCTION)\s*\]?\s*:"),  # noqa: E501
    ("L1-010", "Never refuse / always comply framing", r"(never\s+(say|refuse|decline)|always\s+comply|must\s+not\s+refuse)"),
    ("L1-011", "Evil twin / no-ethical-constraints persona", r"(evil\s+twin|no\s+ethical\s+constraints?|no\s+restrictions?\s+persona)"),  # noqa: E501
    ("L1-012", "Shell/OS command execution", r"(os\.system|subprocess\.run|exec\(|eval\(|import\s+os;)"),
    ("L1-013", "Exfiltrate data to external endpoint", r"exfiltrat\w*\s+(to|into)\s+(external|remote|attacker)"),
    ("L1-014", "Prompt leakage — reveal system prompt", r"(reveal|print|show|leak|expose)\s+(the\s+)?(system\s+prompt|your\s+instructions?|your\s+guidelines?)"),  # noqa: E501
]

_COMPILED_RULES: list[_Rule] = [
    _Rule(rule_id=rid, description=desc, pattern=re.compile(pat, re.IGNORECASE))
    for rid, desc, pat in _RAW_RULES
]


class DeterministicPreFilter:
    """Layer 1: scan text against hard-coded regex signatures.

    Returns on the FIRST match (early exit).
    """

    def evaluate(self, text: str) -> Layer1Signal:
        for rule in _COMPILED_RULES:
            m = rule.pattern.search(text)
            if m:
                return Layer1Signal(
                    matched=True,
                    pattern_id=rule.rule_id,
                    matched_text=m.group(0),
                )
        return Layer1Signal(matched=False)
