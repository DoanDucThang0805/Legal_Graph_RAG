"""Thin entrypoint for Phase 4 batch retrieval."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.retrieval.run_retrieval import run_retrieval_batch


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    summary = run_retrieval_batch(
        input_path=args.input_path,
        output_path=args.output_path,
        limit=args.limit,
        start=args.start,
        top_k=args.top_k,
        max_articles=args.max_articles,
        min_score=args.min_score,
    )
    logging.getLogger(__name__).info("Summary: %s", summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 4 hybrid retrieval over analyzed test questions.")
    parser.add_argument("--input-path", default="data/processed/test_questions_analyzed.parquet")
    parser.add_argument("--output-path", default="data/outputs/retrieval_results.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-articles", type=int, default=None)
    parser.add_argument("--min-score", type=float, default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
