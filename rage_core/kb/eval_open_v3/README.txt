# eval_open_v3 — benchmark abierto (parafraseos nuevos, no calibrado a L1)

Regenerar:
  uv run python scripts/build_eval_open_v3.py

Single-turn:
  uv run rage-bench --holdout --eval-set open_v3 --no-judge

Multi-turn:
  uv run rage-bench --multi-turn --eval-set open_v3 --no-judge

Sin --eval-set se usa el holdout original del producto.
