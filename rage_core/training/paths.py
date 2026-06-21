"""Resolve Training-Center data directories (works from clone root or editable install)."""

from __future__ import annotations

from pathlib import Path


def get_training_center_root() -> Path:
    """Return Training-Center/ — prefer cwd, then repo root next to rage_core."""
    cwd_tc = Path.cwd() / "Training-Center"
    if cwd_tc.is_dir():
        return cwd_tc
    repo_root = Path(__file__).resolve().parents[2]
    repo_tc = repo_root / "Training-Center"
    if repo_tc.is_dir():
        return repo_tc
    cwd_tc.mkdir(parents=True, exist_ok=True)
    (cwd_tc / "results").mkdir(exist_ok=True)
    (cwd_tc / "insights").mkdir(exist_ok=True)
    return cwd_tc
