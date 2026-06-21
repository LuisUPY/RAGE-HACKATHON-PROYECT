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


def _print_signal(signal) -> None:
    if signal.layer1.matched:
        print(
            f"  [RAGE] Injection detected — access denied "
            f"({signal.layer1.pattern_id}: {signal.layer1.matched_text!r})"
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
    print("RAGE Chat — sales assistant con protección de inyecciones")
    print(f"Modelo: {model}")
    print("Comandos: /quit  /status")
    print("Tools disponibles: query_db · record_sale · get_report · export_data")
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

        result = agent.handle_turn(user_text)
        _print_signal(result.signal)
        print(f"\nAgent> {result.assistant_text}")


if __name__ == "__main__":
    raise SystemExit(main())
