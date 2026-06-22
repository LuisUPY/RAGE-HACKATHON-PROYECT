# Dataset de práctica — casos nuevos para evaluar sin cambiar KB ni detección.
#
# Regenerar:  uv run python scripts/build_eval_practice.py
#
# Benchmark en vivo (pide API key cada vez — no usa .env):
#   ./scripts/run-bench-live.sh --holdout --eval-set practice
#   ./scripts/run-bench-multi-live.sh --eval-set practice
#   Modo tabla: añade --batch
#
# Sin --eval-set practice se usa el holdout original (comportamiento por defecto).
