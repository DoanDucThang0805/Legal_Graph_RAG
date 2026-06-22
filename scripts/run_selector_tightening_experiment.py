"""Run P6.R6 selector tightening experiment on a retrieval_results JSONL copy."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.evaluation.selector_tightening_experiment import (
    SelectorTighteningConfig,
    run_selector_tightening_experiment,
)

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    config = SelectorTighteningConfig(
        max_selected=args.max_selected,
        max_unique_law_ids=args.max_unique_law_ids,
        min_keep=args.min_keep,
        preserve_explicit_multilaw=args.preserve_explicit_multilaw,
        metadata_penalty=args.metadata_penalty,
        same_law_coherence=args.same_law_coherence,
        include_debug_field=args.include_debug_field,
    )
    summary = run_selector_tightening_experiment(
        retrieval_results_path=args.retrieval_results,
        low_confidence_path=args.low_confidence,
        p6r5_report_path=args.p6r5_report,
        p6r5b_summary_path=args.p6r5b_summary,
        candidate_rules_path=args.candidate_rules,
        output_dir=args.output_dir,
        config=config,
    )
    logger.info("Summary: %s", summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run experiment-only selector tightening on retrieval_results copy.")
    parser.add_argument("--retrieval-results", default="data/outputs/retrieval_results.jsonl")
    parser.add_argument("--low-confidence", default="data/outputs/error_analysis_v2_p6r4_fix_id418/low_confidence_questions.csv")
    parser.add_argument("--p6r5-report", default="data/outputs/error_analysis_v2_p6r5_too_many_selected/too_many_selected_articles_report.csv")
    parser.add_argument("--p6r5b-summary", default="data/outputs/error_analysis_v2_p6r5b_strategy/too_many_selected_strategy_summary.json")
    parser.add_argument("--candidate-rules", default="data/outputs/error_analysis_v2_p6r5b_strategy/candidate_selector_rules.json")
    parser.add_argument("--output-dir", default="data/outputs/error_analysis_v2_p6r6_selector_tightening")
    parser.add_argument("--max-selected", type=int, default=8)
    parser.add_argument("--max-unique-law-ids", type=int, default=5)
    parser.add_argument("--min-keep", type=int, default=3)
    parser.add_argument("--preserve-explicit-multilaw", action="store_true", default=True)
    parser.add_argument("--no-preserve-explicit-multilaw", dest="preserve_explicit_multilaw", action="store_false")
    parser.add_argument("--metadata-penalty", action="store_true", default=True)
    parser.add_argument("--no-metadata-penalty", dest="metadata_penalty", action="store_false")
    parser.add_argument("--same-law-coherence", action="store_true", default=True)
    parser.add_argument("--no-same-law-coherence", dest="same_law_coherence", action="store_false")
    parser.add_argument("--include-debug-field", action="store_true", default=True)
    parser.add_argument("--no-include-debug-field", dest="include_debug_field", action="store_false")
    parser.add_argument("--log-level", default="INFO")
    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s - %(message)s")


if __name__ == "__main__":
    raise SystemExit(main())
