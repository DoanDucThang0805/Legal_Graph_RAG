"""Thin entrypoint for Phase 1 corpus build."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.knowledge_processing.build_corpus import build_phase1_corpus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 1 Legal Graph RAG corpus.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip a step when its expected output parquet already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    build_phase1_corpus(skip_existing=args.skip_existing)


if __name__ == "__main__":
    main()
