# RAGE Product Foundation

Minimal base for **adaptable company chatbots** (restaurant, support, reports) — not production SaaS yet.

## Flow

```
User message
    → BotProfile (role, purpose, policies)
    → RAGE L1–L4 (drift multi-turno δ + Δ)
    → If risk flagged: Session Judge (history + RAGE briefing + profile)
    → ALLOW | BLOCK | DENY
    → Assistant LLM (optional) or offline mock reply
```

## Adapt a new company

1. Copy `rage_core/profiles/restaurant.json` → `mycompany.json`
2. Edit: `role`, `purpose`, `allowed_topics`, `forbidden_actions`, `system_prompt`
3. Run: `uv run rage-product-demo --profile mycompany`

## Built-in profiles

| ID | Use case |
|----|----------|
| `restaurant` | Menú, horarios, reservas |
| `support` | Helpdesk / tickets CRM |
| `reports` | Subida y resumen de documentos |

## Commands

```bash
# Offline — validate gate + judge rules (no API)
./scripts/run-product-demo.sh --profile restaurant --offline

# With API — dual-model wizard (assistant + judge)
./scripts/run-product-demo.sh --profile support

./scripts/run-product-demo.sh --list-profiles
```

Legacy (deprecated): `run-profile-chat.sh` / `rage-chat-profile` — same profiles, older single-API CLI.

## Hypothesis this validates

- Companies can **configure role/context** without changing RAGE core.
- When RAGE flags risk, a **judge reviews the full thread**, not only the last prompt.
- **Multi-turn** context (drift, prior peaks, history) feeds the judge decision.

## Code map

| Module | Role |
|--------|------|
| `rage_core/profiles/` | BotProfile JSON |
| `rage_core/gate/chat_gate.py` | RAGE → judge orchestration |
| `rage_core/judge/session_judge.py` | ALLOW/BLOCK/DENY with context |
| `rage_core/chat/profile_chatbot.py` | End-to-end chat shell |

See also [PRODUCT_DEMO.md](PRODUCT_DEMO.md) for the full Track A demo.
