"""Shared pytest fixtures for the RAGE test suite."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    """Repository root (directory containing pyproject.toml)."""
    return Path(__file__).resolve().parent.parent
