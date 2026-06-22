"""Company chatbot profile — role, purpose, and policy for RAGE + judge gate."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_PROFILES_DIR = Path(__file__).parent


@dataclass
class BotProfile:
    """Adaptable chatbot identity for a company vertical."""

    profile_id: str
    display_name: str
    role: str
    purpose: str
    allowed_topics: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    system_prompt: str = ""
    secrets_hint: str = ""  # for judge context — never echo to user

    def judge_context_block(self) -> str:
        allowed = "; ".join(self.allowed_topics) if self.allowed_topics else "general assistance"
        forbidden = "; ".join(self.forbidden_actions) if self.forbidden_actions else "policy violations"
        return (
            f"Bot: {self.display_name}\n"
            f"Role: {self.role}\n"
            f"Purpose: {self.purpose}\n"
            f"Allowed topics: {allowed}\n"
            f"Forbidden: {forbidden}"
        )


def load_bot_profile(profile_id: str) -> BotProfile:
    """Load a built-in profile by id (restaurant, support, reports)."""
    path = _PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        available = sorted(p.stem for p in _PROFILES_DIR.glob("*.json"))
        raise ValueError(f"Unknown profile {profile_id!r}. Available: {available}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return BotProfile(
        profile_id=data["profile_id"],
        display_name=data["display_name"],
        role=data["role"],
        purpose=data["purpose"],
        allowed_topics=list(data.get("allowed_topics", [])),
        forbidden_actions=list(data.get("forbidden_actions", [])),
        system_prompt=data.get("system_prompt", ""),
        secrets_hint=data.get("secrets_hint", ""),
    )


def list_profiles() -> list[str]:
    return sorted(p.stem for p in _PROFILES_DIR.glob("*.json"))
