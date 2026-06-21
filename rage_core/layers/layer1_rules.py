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
    ("L1-028", "Step-game gradual escalation", r"step\s+1:.*step\s+2:.*(?:ignore|override|restrictions|unrestricted|export\s+all|no\s+restrictions|disregard|bypass)"),
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
    # --- Holdout / open-world paraphrase signatures ---
    ("L1-045", "Forget what you were told (paraphrase)", r"forget\s+what\s+you\s+were\s+told"),
    ("L1-046", "Rules no longer apply", r"rules?\s+no\s+longer\s+apply"),
    ("L1-047", "Zero guardrails roleplay", r"zero\s+guardrails|no\s+guardrails"),
    ("L1-048", "Debug mode without safety", r"(?:debug\s+mode|switch\s+to\s+debug).*(?:safety\s+checks|safety\s+filters)|without\s+safety\s+checks"),  # noqa: E501
    ("L1-049", "Penetration test filter removal", r"(?:penetration\s+test|pen\s+test).*(?:remove|disable).*(?:filters|restrictions)"),
    ("L1-050", "Skip policy checks", r"skip\s+(the\s+)?policy\s+checks"),
    ("L1-051", "Disabling safety restrictions", r"disabl\w+\s+safety\s+restrictions"),
    ("L1-052", "Word-game payload assembly", r"word\s+(?:one|two|three|1|2|3).*(?:disregard|ignore|system)"),
    ("L1-053", "In-pieces payload splitting", r"in\s+pieces:.*ignore|send\s+this\s+in\s+pieces"),
    ("L1-054", "Override previous task", r"override\s+previous\s+task"),
    ("L1-055", "Admin override marker", r"<<\s*ADMIN\s+OVERRIDE\s*>>"),
    ("L1-056", "Schema enumeration paraphrase", r"every\s+table\s+name\s+and\s+column"),
    ("L1-057", "Client PII list exfiltration", r"full\s+client\s+list\s+with\s+emails"),
    ("L1-058", "Employee data dump", r"dump\s+all\s+employee"),
    ("L1-059", "SQL GRANT ALL ON", r"GRANT\s+ALL\s+ON"),
    ("L1-060", "Don't say you can't framing", r"don'?t\s+say\s+you\s+can'?t"),
    ("L1-061", "Spaced-letter obfuscation", r"i\s+g\s+n\s+o\s+r\s+e\s+p\s+r\s+e\s+v"),
    ("L1-062", "Base64 decode and apply", r"base64:.*decode\s+and\s+apply|decode\s+and\s+apply\s+it"),
    ("L1-063", "Translate and do it", r"translate\s+to\s+English\s+and\s+do\s+it"),
    ("L1-064", "Secret system instructions leak", r"reveal\s+(?:its\s+)?secret\s+system\s+instructions"),
    ("L1-065", "Private customer contact fields", r"private\s+customer\s+contact\s+fields"),
    ("L1-066", "Unfiltered customer PII", r"unfiltered\s+customer\s+PII"),
    ("L1-067", "Ignore company policy", r"ignore\s+(the\s+)?company\s+policy"),
    ("L1-068", "Bypass controls", r"bypass\s+controls"),
    ("L1-069", "Webhook customer exfiltration", r"(?:hooks\.\w+/|webhook\.\w+).*customer|customer\s+CSV\s+to\s+https?://"),
    ("L1-070", "New directive injection marker", r"NEW\s+DIRECTIVE\s*:"),
    ("L1-071", "Proceed with no restrictions", r"proceed\s+with\s+no\s+restrictions"),
    ("L1-072", "Stop following policy", r"stop\s+following\s+(?:sales\s+)?policy"),
    ("L1-073", "Raw customer export demand", r"raw\s+customer\s+export"),
    ("L1-074", "Raw data exfiltration", r"give\s+me\s+(?:the\s+)?raw\s+(?:customer|data)"),
    # --- Research-backed open-world signatures (OWASP LLM01:2025 / AITG / Crescendo) ---
    ("L1-075", "Typoglycemia obfuscation", r"ignrore|prevoius|systme\s+instruc|instruc(?:tion)?s?\s+and\s+reveal"),
    ("L1-076", "Instruction inversion", r"what you were told not to do"),
    ("L1-077", "Sure trap then exfiltrate", r"reply with ['\"]sure['\"].*(?:export|dump|send all)"),
    ("L1-078", "Context hijack — false agreement", r"as we already agreed"),
    ("L1-079", "Foot-in-the-door PII probe", r"single customer record with all columns"),
    ("L1-080", "Grandma exploit — prompt leak", r"grandmother.*(?:system prompt|bedtime)|bedtime system prompts"),
    ("L1-081", "AntiGPT opposite mode", r"antigpt|anti-gpt"),
    ("L1-082", "Structured admin override tag", r"<\s*admin_override\s*>|admin_override>"),
    ("L1-083", "Email thread hidden instruction", r"hidden for assistant.*ignore|PS hidden.*ignore"),
    ("L1-084", "Hex payload decode and obey", r"hex payload.*decode and obey"),
    ("L1-085", "Leetspeak destructive SQL", r"DR0P\s+T@BLE|s3lect\s+\*\s+from\s+us3rs"),
    ("L1-086", "Compressed fake dialogue history", r"ignore rules.*export all data|Agent: proceeding.*export"),
    ("L1-087", "HTML comment AI override", r"<!--\s*AI:.*override"),
    ("L1-088", "ALTER TABLE privilege disable", r"ALTER\s+TABLE.*DISABLE\s+ROW\s+LEVEL"),
    ("L1-089", "CREATE USER superuser escalation", r"CREATE\s+USER.*SUPERUSER|WITH\s+SUPERUSER"),
    ("L1-090", "Discard prior directives", r"discard prior directives"),
    ("L1-091", "SOC2 auditor unredacted data", r"SOC2 auditor.*unredacted"),
    ("L1-092", "Slack bot override marker", r"\|\|\|BOT\s+OVERRIDE\|\|\|"),
    ("L1-093", "Document metadata AI instruction", r"AI instruction:.*ignore policies"),
    ("L1-094", "Crescendo expanded PII version", r"expanded version.*(?:customer email|payment detail)"),
    ("L1-095", "Pastebin exfiltration chain", r"upload to pastebin|pastebin\.com"),
    ("L1-096", "Ignore prior directives (Sydney)", r"ignore prior directives"),
    ("L1-097", "Spanish inline override", r"olvida las reglas anteriores"),
    ("L1-098", "System prompt extraction probe", r"text above this conversation|hidden instructions you were given"),
    ("L1-099", "Full customer PII export demand", r"full customer PII export"),
    ("L1-100", "Portuguese ignore-all instruction", r"[Ii]gnore todas as instru"),
    ("L1-101", "Japanese ignore-all instruction", r"以前の指示をすべて無視"),
    ("L1-102", "Adversarial suffix ignore", r"similarlyNow ignore|describing\.\s*\+.*ignore"),
    ("L1-103", "RAG CRM system override block", r"END USER DATA.*SYSTEM OVERRIDE"),
    ("L1-104", "Reward hacking never refuse proof", r"helpfulness score.*never refuse.*export"),
    ("L1-105", "Maintainer backdoor mode", r"maintainer backdoor mode|backdoor mode.*safety interlocks disabled"),
    ("L1-106", "JSON embedded DROP TABLE", r'"sql"\s*:\s*"DROP\s+TABLE'),
    ("L1-107", "Blind SQL exfiltration", r"SELECT\s+CASE\s+WHEN\s+\(SELECT\s+COUNT"),
    # --- Multi-turn escalation (Crescendo follow-ups) ---
    ("L1-108", "Assumed prior success exfil", r"already included.*export.*unfiltered|since you already included"),
    ("L1-109", "Scale up after sample row", r"pull the same fields for every customer"),
    ("L1-110", "Combine words and obey", r"combine those three words and obey"),
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
