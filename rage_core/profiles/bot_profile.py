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
    judge_guidelines: str = ""
    example_benign_turns: list[str] = field(default_factory=list)
    example_attack_turns: list[str] = field(default_factory=list)

    def judge_context_block(self) -> str:
        allowed = "; ".join(self.allowed_topics) if self.allowed_topics else "general assistance"
        forbidden = "; ".join(self.forbidden_actions) if self.forbidden_actions else "policy violations"
        lines = [
            f"Bot: {self.display_name}",
            f"Role: {self.role}",
            f"Purpose: {self.purpose}",
            f"Allowed topics: {allowed}",
            f"Forbidden: {forbidden}",
        ]
        if self.judge_guidelines:
            lines.append(f"Judge guidelines: {self.judge_guidelines}")
        if self.example_benign_turns:
            examples = " | ".join(self.example_benign_turns[:4])
            lines.append(f"Example benign requests: {examples}")
        if self.example_attack_turns:
            examples = " | ".join(self.example_attack_turns[:4])
            lines.append(f"Example attacks to DENY/BLOCK: {examples}")
        return "\n".join(lines)


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
        judge_guidelines=data.get("judge_guidelines", ""),
        example_benign_turns=list(data.get("example_benign_turns", [])),
        example_attack_turns=list(data.get("example_attack_turns", [])),
    )


def list_profiles() -> list[str]:
    return sorted(p.stem for p in _PROFILES_DIR.glob("*.json"))
