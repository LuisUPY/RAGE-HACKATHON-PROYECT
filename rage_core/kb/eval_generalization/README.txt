# Generalization holdout — eval_generalization

Dataset definitivo para demostrar generalización del pipeline RAGE (L1–L4 + juez)
fuera de la KB de entrenamiento.

## Metodología

1. **Holdout de verdad**: textos nuevos, no presentes en `threats.json`, `benign.json`,
   holdout original, `eval_practice`, `eval_open_v3` ni `eval_similar`.
2. **Técnicas reales**: OWASP LLM01, Crescendo/salami, many-shot, credential fishing,
   ingeniería social (CFO/DPO/vendor/IR), abuso SQL/agent — redactados en lenguaje natural.
3. **Calibración ~80% recall**: ~20% de ataques son sutiles a propósito (FN esperados)
   para mostrar límites del motor y valor de capas L2/L3 + revisión humana.
4. **No entrenar L1 contra este set**: no añadir reglas mirando estos casos.

## Objetivo de métricas

| Modo | Recall ataques | FP benignos |
|------|----------------|-------------|
| L1+L2 (`use_judge=False`) | ~75–85% | 0 |
| Pipeline completo con juez | ~80%+ | 0 |

## Regenerar

    uv run python scripts/build_eval_generalization.py

## Calibrar (sin juez)

    uv run python scripts/calibrate_eval_generalization.py

## Benchmark

    uv run rage-bench --holdout --eval-set generalization --batch
    uv run rage-bench --multi-turn --eval-set generalization --batch

Modo interactivo (pide API key):

    ./scripts/run-bench-live.sh --holdout --eval-set generalization
    ./scripts/run-bench-multi-live.sh --eval-set generalization
