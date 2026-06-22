"""Design a strategy report for too_many_selected_articles diagnostics."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.evaluation.too_many_selected_strategy import build_too_many_selected_strategy

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    summary = build_too_many_selected_strategy(
        p6r5_report_path=args.p6r5_report,
        p6r5_summary_path=args.p6r5_summary,
        law_distribution_path=args.law_distribution,
        samples_md_path=args.samples_md,
        retrieval_results_path=args.retrieval_results,
        generated_answers_path=args.generated_answers,
        output_dir=args.output_dir,
    )
    logger.info("Summary: %s", summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Design selector/retrieval strategy from P6.R5 too_many_selected reports.")
    parser.add_argument("--p6r5-report", default="data/outputs/error_analysis_v2_p6r5_too_many_selected/too_many_selected_articles_report.csv")
    parser.add_argument("--p6r5-summary", default="data/outputs/error_analysis_v2_p6r5_too_many_selected/too_many_selected_articles_summary.json")
    parser.add_argument("--law-distribution", default="data/outputs/error_analysis_v2_p6r5_too_many_selected/too_many_selected_articles_law_distribution.csv")
    parser.add_argument("--samples-md", default="data/outputs/error_analysis_v2_p6r5_too_many_selected/too_many_selected_articles_samples.md")
    parser.add_argument("--retrieval-results", default="data/outputs/retrieval_results.jsonl")
    parser.add_argument("--generated-answers", default="data/outputs/generated_answers_v2_p6r4_merged_for_eval_fix_id418.jsonl")
    parser.add_argument("--output-dir", default="data/outputs/error_analysis_v2_p6r5b_strategy")
    parser.add_argument("--log-level", default="INFO")
    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s - %(message)s")


if __name__ == "__main__":
    raise SystemExit(main())
