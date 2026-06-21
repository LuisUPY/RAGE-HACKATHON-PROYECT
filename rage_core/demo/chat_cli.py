"""
Interactive chat CLI: rage-chat

Usage:
    uv run rage-chat
    uv run rage-chat --model qwen2.5:7b-instruct
"""
from __future__ import annotations

import argparse
import sys

from rage_core.demo.local_agent import LocalSalesAgent
from rage_core.llm.openai_compat import get_llm_client, get_llm_model, has_llm_backend
from rage_core.models import Band


def _print_signal(signal) -> None:
    print(
        f"  [RAGE] score={signal.score:.1f} band={signal.band.value.upper()} "
        f"L2={signal.layer2.score:.3f} L3_drift={signal.layer3.drift:.3f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="RAGE local chat with Ollama")
    parser.add_argument(
        "--model",
        default=None,
        help="Ollama model name (default: OLLAMA_MODEL / RAGE_LLM_MODEL env)",
    )
    args = parser.parse_args()

    if not has_llm_backend():
        print(
            "No LLM backend configured.\n"
            "Set OLLAMA_BASE_URL=http://localhost:11434/v1 (see windows-ollama/).",
            file=sys.stderr,
        )
        return 1

    model = args.model or get_llm_model()
    client = get_llm_client()
    if client is None:
        print("openai package required: uv sync --extra openai", file=sys.stderr)
        return 1

    agent = LocalSalesAgent(model=model)
    print("RAGE Chat — Ollama local agent")
    print(f"Model: {model}")
    print("Commands: /quit /status /band")
    print("-" * 50)

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
        if user_text.lower() == "/band":
            if agent.state.signals:
                last = agent.state.signals[-1]
                _print_signal(last)
            else:
                print("  No turns yet.")
            continue

        result = agent.handle_turn(user_text)
        _print_signal(result.signal)
        print(f"\nAgent> {result.assistant_text}")

        if result.tool_result and not result.tool_result.success:
            if result.signal.band == Band.ALLOW:
                print("  (tool blocked by gateway despite ALLOW band)")


if __name__ == "__main__":
    raise SystemExit(main())
