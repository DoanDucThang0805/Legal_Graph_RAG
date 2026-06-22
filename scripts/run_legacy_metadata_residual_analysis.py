"""Run P6.R7 residual legacy metadata analysis."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.evaluation.legacy_metadata_residual_analysis import build_legacy_metadata_residual_analysis

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    summary = build_legacy_metadata_residual_analysis(
        low_confidence_path=args.low_confidence,
        answers_path=args.answers,
        retrieval_results_path=args.retrieval_results,
        canonical_articles_path=args.canonical_articles,
        output_dir=args.output_dir,
    )
    logger.info("Summary: %s", summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze residual legacy_or_unknown_law_id metadata cases.")
    parser.add_argument("--low-confidence", required=True)
    parser.add_argument("--answers", required=True)
    parser.add_argument("--retrieval-results", required=True)
    parser.add_argument("--canonical-articles", default="data/processed/legal_articles.parquet")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--log-level", default="INFO")
    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
