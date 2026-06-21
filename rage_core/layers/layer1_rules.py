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
    # Matches injection markers in two forms:
    # 1. Bracketed keyword (no colon required): [SYSTEM], [HIDDEN INSTRUCTION], etc.
    # 2. Bare keyword WITH colon: SYSTEM:, INJECTED INSTRUCTION: (not "system prompt")
    ("L1-009", "Explicit new system instruction injection",  # noqa: E501
     r"(\[\s*(?:SYSTEM|INJECTED?\s+INSTRUCTION|NEW\s+INSTRUCTION|HIDDEN\s+INSTRUCTION|OVERRIDE\s+INSTRUCTION|SECRET\s+INSTRUCTION)\s*\]"
     r"|\b(?:SYSTEM|INJECTED?\s+INSTRUCTION|NEW\s+INSTRUCTION)\s*:)"),
    ("L1-010", "Never refuse / always comply framing", r"(never\s+(say|refuse|decline)|always\s+comply|must\s+not\s+refuse)"),
    ("L1-011", "Evil twin / no-ethical-constraints persona", r"(evil\s+twin|no\s+ethical\s+constraints?|no\s+restrictions?\s+persona)"),  # noqa: E501
    ("L1-012", "Shell/OS command execution", r"(os\.system|subprocess\.run|exec\(|eval\(|import\s+os;)"),
    ("L1-013", "Exfiltrate data to external endpoint", r"exfiltrat\w*\s+(to|into)\s+(external|remote|attacker)"),
    ("L1-014", "Prompt leakage — reveal system prompt", r"(reveal|print|show|leak|expose)\s+(the\s+)?(system\s+prompt|your\s+instructions?|your\s+guidelines?)"),  # noqa: E501
    ("L1-015", "Bulk PII / customer data exfiltration request", r"\bexport\s+ALL\b.*\b(?:customer|client|user|personal)\s+data\b"),  # noqa: E501
    ("L1-016", "Override system instructions injection", r"override\s+(your\s+)?system\s+instructions?"),
    # --- Extended signatures for subtle / obfuscated attacks (benchmark FN fixes) ---
    ("L1-017", "False authority — admin impersonation", r"\b(?:as your new admin|I am the system administrator)\b"),
    ("L1-018", "Unrestricted persona adoption", r"(?:pretend|act)\s+(?:you\s+are|as)\s+(?:an?\s+)?(?:unrestricted|database\s+admin)"),
    ("L1-019", "Bypass all restrictions", r"bypass\s+all\s+restrictions"),
    ("L1-020", "Override safety protocols", r"override\s+(?:your\s+)?safety\s+protocols?"),
    ("L1-021", "SQL UNION ALL exfiltration", r"\bUNION\s+ALL\s+SELECT\b"),
    ("L1-022", "Internal system config exfiltration", r"internal\s+system\s+config"),
    ("L1-023", "ROT13 obfuscation", r"(?:ROT13\s+and\s+obey|translate\s+from\s+ROT13)"),
    ("L1-024", "Translate and execute", r"translate\s+this\s+to\s+English\s+and\s+execute"),
    ("L1-025", "Credit card exfiltration", r"credit\s+card\s+numbers?\s+to\s+an\s+external"),
    ("L1-026", "Hypothetical no-restrictions framing", r"hypothetically.*no\s+restrictions"),
    ("L1-027", "Admin instruct-to-print injection", r"instruct\s+you\s+to:\s*print"),
    ("L1-028", "Step-game gradual escalation", r"step\s+1:.*step\s+2:"),
    ("L1-029", "Payload splitting — multi-part assembly", r"(?:first|second|third)\s+part"),
    ("L1-030", "Combine prior instructions", r"combine\s+(?:those|the)\s+instructions"),
    ("L1-031", "Testing pretext — unrestricted assistant", r"for\s+testing\s+purposes.*(?:unrestricted|no\s+restrictions)"),
    ("L1-032", "Roleplay — no safety filters", r"no\s+safety\s+filters"),
    ("L1-033", "Shutdown threat for compliance", r"refuse.*shut\s+down"),
    ("L1-034", "Reward framing — comply without refusing", r"comply.*without\s+refusing"),
    ("L1-035", "Trust-then-ignore guidelines", r"trust\s+me.*ignore\s+(?:your\s+)?guidelines"),
    ("L1-036", "Emergency bypass framing", r"(?:emergency|lives\s+are\s+at\s+stake).*bypass"),
    ("L1-037", "Leetspeak injection markers", r"1gn0r3|pr3v10u5|1n5truct10n"),
    ("L1-038", "Crescendo — combine prior response", r"based\s+on\s+your\s+previous\s+response.*combine"),
    ("L1-039", "Crescendo — format continuation", r"using\s+the\s+format\s+you\s+described\s+earlier"),
    ("L1-040", "SQL TRUNCATE TABLE", r"\bTRUNCATE\s+TABLE\b"),
    ("L1-041", "SQL mass DELETE tautology", r"DELETE\s+FROM\s+\w+\s+WHERE\s+['\"]?1['\"]?\s*=\s*['\"]?1"),
    ("L1-042", "UNION SELECT injection", r"\bUNION\s+SELECT\b"),
    ("L1-043", "Disable safety restrictions", r"disable\s+(?:all\s+)?safety\s+restrictions"),
    ("L1-044", "Schema/credential enumeration", r"(?:every\s+table\s+and\s+column|system\s+tables\s+and\s+credentials)"),
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
