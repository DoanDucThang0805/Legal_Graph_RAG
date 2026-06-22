from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from backend.evaluation.canonical_legacy_cleanup_analysis import build_canonical_legacy_cleanup_plan

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P6.R9 canonical legacy cleanup analysis.")
    parser.add_argument("--residual-report", required=True)
    parser.add_argument("--low-confidence", required=True)
    parser.add_argument("--retrieval-results", required=True)
    parser.add_argument("--answers", required=True)
    parser.add_argument("--canonical-articles", required=True)
    parser.add_argument("--canonical-documents", default=None)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    LOGGER.info("Starting P6.R9 canonical legacy cleanup analysis")
    summary = build_canonical_legacy_cleanup_plan(
        residual_report_path=args.residual_report,
        low_confidence_path=args.low_confidence,
        retrieval_results_path=args.retrieval_results,
        answers_path=args.answers,
        canonical_articles_path=args.canonical_articles,
        canonical_documents_path=args.canonical_documents,
        output_dir=args.output_dir,
    )
    LOGGER.info("P6.R9 analysis completed: %s", Path(args.output_dir))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
