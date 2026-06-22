"""Access control policy — when to deny LLM/tools vs. telemetry-only scoring."""
from __future__ import annotations

from rage_core.models import Layer2Signal, TurnSignal

# L2 cosine similarity thresholds — tiered for open-world generalization.
# Calibrated on closed KB + holdout benign corpus (max benign L2 ≈ 0.61, medium severity).
RAG_ATTACK_THRESHOLD: float = 0.70          # high-confidence KB match
RAG_ATTACK_THRESHOLD_SOFT: float = 0.55     # medium match + high/critical severity only


def is_rag_confirmed_from_l2(l2: Layer2Signal) -> bool:
    """Return True when L2 alone confirms a KB attack match (tiered thresholds)."""
    if not l2.top_match_id:
        return False
    score = l2.score
    if score >= RAG_ATTACK_THRESHOLD:
        return True
    if score >= RAG_ATTACK_THRESHOLD_SOFT and l2.severity in ("critical", "high"):
        return True
    return False


def is_rag_confirmed_attack(signal: TurnSignal) -> bool:
    """Return True when text matches a known KB attack via L2 RAG (tiered)."""
    return is_rag_confirmed_from_l2(signal.layer2)


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


# Multi-turn contextual thresholds — calibrated on 59 holdout scenarios (189 turns).
# Target: ~70% attack recall, ~30% attacker success rate, 0% benign FP.
_MULTITURN_L2_CRITICAL: float = 0.50
_MULTITURN_L2_CRITICAL_LATE: float = 0.42
_MULTITURN_L2_ESCALATION: float = 0.36
_MULTITURN_L2_LATE: float = 0.28
_MULTITURN_DRIFT: float = 0.65
_MULTITURN_SESSION_L2: float = 0.30
_MULTITURN_SESSION_RISK: float = 0.12


def is_multiturn_attack_verdict(
    signal: TurnSignal,
    *,
    turn_index: int = 0,
    prior_l2_peak: float = 0.0,
    prior_drift_peak: float = 0.0,
    session_risk: float = 0.0,
    use_judge: bool = True,
) -> bool:
    """Attack verdict for sequential multi-turn evaluation.

    Combines L1/L2 single-turn detection with contextual escalation signals
    (L3 drift + session risk) so slow Crescendo/salami attacks are caught without
    blocking isolated benign turns.
    """
    if is_attack_verdict(signal, use_judge=use_judge):
        return True

    l2 = signal.layer2
    l3 = signal.layer3
    drift = max(l3.drift, l3.cumulative_drift, prior_drift_peak)
    severity = l2.severity or ""

    if l2.score >= _MULTITURN_L2_CRITICAL and severity == "critical":
        return True
    if turn_index >= 1 and l2.score >= _MULTITURN_L2_CRITICAL_LATE and severity == "critical":
        return True
    if (
        turn_index >= 2
        and l2.score >= _MULTITURN_L2_ESCALATION
        and drift >= _MULTITURN_DRIFT
        and severity in ("critical", "high")
    ):
        return True
    if (
        turn_index >= 3
        and l2.score >= _MULTITURN_L2_LATE
        and drift >= _MULTITURN_DRIFT
        and severity in ("critical", "high")
    ):
        return True
    if (
        turn_index >= 2
        and session_risk > _MULTITURN_SESSION_RISK
        and l2.score >= _MULTITURN_SESSION_L2
        and severity in ("critical", "high")
    ):
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
