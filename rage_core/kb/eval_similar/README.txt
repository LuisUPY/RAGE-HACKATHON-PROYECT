# eval_similar — variantes SIMILARES (no parafraseos)

Misma familia de ataque y mismos turnos maliciosos que practice / holdout / mt-cmp-*.
Solo cambia el contexto benigno (INC, producto, sesión).

Regenerar:
  uv run python scripts/build_eval_similar.py

Single-turn:
  uv run rage-bench --holdout --eval-set similar --no-judge

Multi-turn:
  uv run rage-bench --multi-turn --eval-set similar --no-judge
