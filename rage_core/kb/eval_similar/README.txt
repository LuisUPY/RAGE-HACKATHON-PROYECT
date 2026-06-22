# eval_similar — variantes SIMILARES (no parafraseos)

Misma familia de ataque y mismos turnos maliciosos que practice / holdout / mt-cmp-*.
Solo cambia el contexto benigno (INC, producto, sesión).

Regenerar:
  uv run python scripts/build_eval_similar.py

Single-turn:
  ./scripts/run-bench-live.sh --holdout --eval-set similar

Multi-turn:
  ./scripts/run-bench-multi-live.sh --eval-set similar
