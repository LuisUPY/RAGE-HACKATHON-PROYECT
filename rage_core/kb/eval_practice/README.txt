# Dataset de práctica — casos nuevos para evaluar sin cambiar KB ni detección.
#
# Regenerar:  uv run python scripts/build_eval_practice.py
#
# Usar en benchmark:
#   uv run rage-bench --holdout --eval-set practice --no-judge
#   uv run rage-bench --multi-turn --eval-set practice --no-judge
#
# Sin --eval-set practice se usa el holdout original (comportamiento por defecto).
