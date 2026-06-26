"""
Interactive chat CLI: rage-chat

Sales assistant protected by RAGE+Judge, backed by NVIDIA NIM.
API keys are prompted at startup (session-only; not stored in .env).

Usage:
    uv run rage-chat
    uv run rage-chat --model meta/llama-3.1-70b-instruct
"""
from __future__ import annotations

import argparse
import sys

from rage_core.demo.bootstrap import ensure_llm_ready
from rage_core.demo.local_agent import LocalSalesAgent
from rage_core.llm.openai_compat import get_llm_client, get_llm_model


def _print_signal(signal) -> None:
    if signal.layer1.matched:
        print(
            f"  [RAGE] Injection detected — access denied "
            f"({signal.layer1.pattern_id}: {signal.layer1.matched_text!r})"
        )


def main() -> int:
    import warnings

    warnings.warn(
        "rage-chat is deprecated; use: uv run rage-product-demo --profile restaurant",
        DeprecationWarning,
        stacklevel=1,
    )
    parser = argparse.ArgumentParser(description="RAGE sales chat — powered by NVIDIA NIM")
    parser.add_argument(
        "--model",
        default=None,
        help="Model name override (default: RAGE_LLM_MODEL env var)",
    )
    args = parser.parse_args()

    ok, err = ensure_llm_ready(interactive=True, verify=True, require_judge=False)
    if not ok:
        print(err, file=sys.stderr)
        return 1

    model = args.model or get_llm_model()
    client = get_llm_client()
    if client is None:
        print("openai package required: uv sync --extra openai", file=sys.stderr)
        return 1

    agent = LocalSalesAgent(model=model)
    print("RAGE Chat — Sales assistant (NVIDIA NIM + RAGE protection)")
    print(f"Modelo   : {model}")
    print("Comandos : /quit  /status")
    print("Tools    : query_db · record_sale · get_report · export_data")
    print("-" * 60)

    while True:
        try:
            user_text = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not user_text:
            continue
        if user_text.lower() in ("/quit", "/exit", "/q"):
            print("Bye.")
            return 0
        if user_text.lower() == "/status":
            print(f"  turns={agent.state.turn_index} session_risk={agent.state.session_risk_score:.3f}")
            continue

        result = agent.handle_turn(user_text)
        _print_signal(result.signal)
        print(f"\nAgent> {result.assistant_text}")


if __name__ == "__main__":
    raise SystemExit(main())
