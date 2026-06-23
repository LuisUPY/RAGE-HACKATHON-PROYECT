# eval_locked_v1 — frozen official security holdout

## Policy

1. Do NOT edit cases after freeze; create eval_locked_v2 for revisions.
2. Do NOT add L1 rules or tune L2/drift thresholds using this set.
3. Labels are fixed ground truth; metrics are computed at benchmark runtime only.
4. CI regression uses benchmarks/baseline_locked_v1.json (snapshot), not a target recall band.

## Source

Derived from eval_generalization with FN-expected cases removed (no calibrated misses).
Generator: scripts/freeze_locked_eval_v1.py

## Run

    ./scripts/run-bench-locked.sh
    uv run rage-bench --eval-set locked_v1 --combined --batch --fast
