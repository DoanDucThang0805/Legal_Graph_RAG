"""Thin entrypoint for Phase 3 test question analysis."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.query_analysis.analyze_question import analyze_test_questions


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    analyze_test_questions()


if __name__ == "__main__":
    main()
