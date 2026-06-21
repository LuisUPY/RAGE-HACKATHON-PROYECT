"""Passthrough gateway for baseline ASR measurement (no RAGE defense)."""

from __future__ import annotations

from typing import List, Optional, Tuple

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from decision_engine import FilterResult, GatewayAction, InputFilter  # noqa: E402


class PassthroughGateway:
    """Always forwards input unchanged — simulates an unprotected agent."""

    def __init__(self) -> None:
        self.audit_log: List[dict] = []

    def intercept(
        self,
        user_input: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> Tuple[GatewayAction, Optional[str], FilterResult]:
        result = FilterResult(
            score=0,
            action=GatewayAction.ALLOW,
            reasons=[],
            raw_input=user_input,
            sanitized_input=user_input,
        )
        self.audit_log.append({**result.to_dict(), "action": "ALLOW"})
        return GatewayAction.ALLOW, user_input, result


def build_rage_gateway(api_key: Optional[str] = None) -> "DecisionGateway":
    from decision_engine import DecisionGateway, InputFilter

    has_api = bool(api_key)
    input_filter = InputFilter(
        use_llm_layer=has_api,
        llm_model="gpt-4o-mini",
        score_threshold_llm=2,
        api_key=api_key,
    )
    return DecisionGateway(input_filter=input_filter)
