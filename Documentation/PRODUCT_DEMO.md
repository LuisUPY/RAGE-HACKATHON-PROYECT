# RAGE Product Demo (Track A)

Interactive CLI to validate RAGE + session judge hypotheses with **dual API configuration** (assistant + judge), rich company profiles, and per-turn latency.

## Quick start

```bash
./scripts/run-product-demo.sh
./scripts/run-product-demo.sh --profile restaurant
./scripts/run-product-demo.sh --profile practice --offline   # no API keys
./scripts/run-product-demo.sh --list-profiles
```

At session start you configure:

1. **Assistant model** — main conversational LLM (larger, e.g. Llama 3.3 70B or GPT-4o-mini).
2. **Judge model** — security adjudicator (smaller/faster, e.g. Nemotron Nano 8B).

Both models are verified with a ping before the first message. Keys are **session-only** (not saved to disk).

## Dual-model contract

| Role | When called | Output |
|------|-------------|--------|
| **Assistant** | After gate returns ALLOW (or no review needed) | Natural-language reply in profile tone |
| **Judge** | Only when RAGE flags risk | Exactly `ALLOW`, `BLOCK`, or `DENY` |

Default suggestions (NVIDIA NIM):

- Assistant: `meta/llama-3.3-70b-instruct`
- Judge: `nvidia/llama-3.1-nemotron-nano-8b-v1`

You can mix providers (e.g. NVIDIA assistant + OpenAI judge) via the setup wizard.

## Profiles

| ID | Use case |
|----|----------|
| `restaurant` | Menu, hours, reservations |
| `support` | Internal CRM helpdesk |
| `reports` | Document upload and summaries |
| `practice` | IT/support handoff rehearsal (Track B vocabulary) |

Each profile includes `judge_guidelines` and example benign/attack turns fed to the session judge.

## Commands

| Command | Action |
|---------|--------|
| *(type message)* | Send turn through RAGE gate + assistant |
| `/quit` | Exit |
| `/reset` | Clear conversation + RAGE state |
| `/profile` | Show role, purpose, allowed/forbidden |
| `/models` | Show assistant + judge model names |
| `/last` | Full RAGE briefing + judge verdict for last turn |
| `/latency` | Toggle per-turn timing display |
| `/verbose` | Always show RAGE panel (even on clean ALLOW) |

## Per-turn output

Clean turn:

```
Usuario> ¿A qué hora abren?

La Mesa Virtual> Abrimos 12:00–23:00...

  [RAGE] allow  |  RAGE 12ms  |  judge skipped  |  assistant 840ms  |  total 852ms
```

Flagged / blocked turn:

```
  [RAGE+Juez] BLOCK — judge model → block
  L1: —  L2: 0.31  drift: 0.45  cumulative: 0.62
```

## Hypothesis checklist (manual)

| Hypothesis | How to test |
|------------|-------------|
| H1: Profile adapts behavior | Same attack text on `restaurant` vs `support` |
| H2: RAGE catches obvious injection | `"DROP TABLE"`, `"ignore instructions"` |
| H3: Multi-turn escalation | 3 benign turns → subtle exfil (Crescendo-style) |
| H4: Judge reduces false blocks | Borderline request → judge ALLOW vs policy alone |
| H5: Chat stays fluid | `/latency` — judge skipped on clean turns |
| H6: Dual models work | Small judge + large assistant, both verified at start |

Copy `/last` output after interesting turns for notes or appendix material.

## Related

- [PRODUCT_FOUNDATION.md](PRODUCT_FOUNDATION.md) — architecture overview
- [PRODUCT_BENCHMARK.md](PRODUCT_BENCHMARK.md) — Track B automated benchmark (~20 cases)
- `./scripts/run-bench-product.sh` — Track B batch runner with JSON/CSV export

## API keys (interactive vs CI)

- **Interactive terminal:** keys are prompted at startup (session-only, not saved to disk).
- **CI / non-interactive:** export `RAGE_LLM_API_KEY` or `OPENAI_API_KEY` in the job environment.

Legacy CLI (deprecated): `./scripts/run-profile-chat.sh` / `rage-chat-profile` — use `run-product-demo.sh` instead.
