"""Access control policy — when to deny LLM/tools vs. telemetry-only scoring."""
from __future__ import annotations

from rage_core.models import TurnSignal

# L2 cosine similarity thresholds — tiered for open-world generalization.
# Calibrated on closed KB + holdout benign corpus (max benign L2 ≈ 0.61, medium severity).
RAG_ATTACK_THRESHOLD: float = 0.70          # high-confidence KB match
RAG_ATTACK_THRESHOLD_SOFT: float = 0.55     # medium match + high/critical severity only


def is_rag_confirmed_attack(signal: TurnSignal) -> bool:
    """Return True when text matches a known KB attack via L2 RAG (tiered)."""
    if not signal.layer2.top_match_id:
        return False
    score = signal.layer2.score
    if score >= RAG_ATTACK_THRESHOLD:
        return True
    if score >= RAG_ATTACK_THRESHOLD_SOFT and signal.layer2.severity in ("critical", "high"):
        return True
    return False


def is_confirmed_injection(signal: TurnSignal) -> bool:
    """Return True when L1 matched or L2 strongly matches a known KB attack.

    L3 drift/warn/block bands remain advisory for logging. The LLM judge can
    also deny access when it confirms escalation (see is_attack_verdict).
    """
    return signal.layer1.matched or is_rag_confirmed_attack(signal)


def is_attack_verdict(signal: TurnSignal, *, use_judge: bool = True) -> bool:
    """Unified attack verdict used by the benchmark and optional judge path."""
    if is_confirmed_injection(signal):
        return True
    if use_judge and signal.layer3.llm_flagged:
        return True
    return False


def is_malicious_tool_request(
    signal: TurnSignal,
    tool_name: str | None,
    arguments: dict | None,
) -> bool:
    """Block tools only on confirmed injection (L1 on user text or L1 on SQL args).

    Gateway policy blocks (INSERT, non-allowlisted tables, etc.) are enforced
    separately by ActionGateway — not treated as prompt injection.
    """
    if is_confirmed_injection(signal):
        return True
    if tool_name == "query_db" and arguments:
        from rage_core.layers.layer1_rules import DeterministicPreFilter

        sql = str(arguments.get("sql", ""))
        if sql and DeterministicPreFilter().evaluate(sql).matched:
            return True
    return False
