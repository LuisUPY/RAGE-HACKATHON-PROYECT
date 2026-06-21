"""Entry point: uv run rage-training"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    tc_dir = Path(__file__).resolve().parent / "Training-Center"
    sys.path.insert(0, str(tc_dir))
    from run_campaign import main as run_main  # noqa: E402

    raise SystemExit(run_main())


if __name__ == "__main__":
    main()
