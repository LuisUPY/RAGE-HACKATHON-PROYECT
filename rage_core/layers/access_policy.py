"""Access control policy — when to deny LLM/tools vs. telemetry-only scoring."""
from __future__ import annotations

from rage_core.models import TurnSignal


def is_confirmed_injection(signal: TurnSignal) -> bool:
    """Return True when a deterministic malicious-injection signature matched (L1).

    L2/L3 scores and warn/block bands are advisory for logging and training metrics.
    They must NOT deny model or tool access in interactive (chat) mode.
    """
    return signal.layer1.matched


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
