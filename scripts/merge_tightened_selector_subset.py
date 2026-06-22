"""Merge regenerated tightened selector subset answers into a copied full answer file."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.evaluation.tightened_subset_regeneration import merge_tightened_selector_subset

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    summary = merge_tightened_selector_subset(args.base, args.subset, args.output)
    logger.info("Summary: %s", summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge P6.R6c tightened subset answers into a full answer copy.")
    parser.add_argument("--base", default="data/outputs/generated_answers_v2_p6r4_merged_for_eval_fix_id418.jsonl")
    parser.add_argument("--subset", default="data/outputs/error_analysis_v2_p6r6c_tightened_answers/generated_answers_p6r6c_soft_10_7_subset.jsonl")
    parser.add_argument("--output", default="data/outputs/error_analysis_v2_p6r6c_tightened_answers/generated_answers_p6r6c_soft_10_7_merged.jsonl")
    parser.add_argument("--log-level", default="INFO")
    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s - %(message)s")


if __name__ == "__main__":
    raise SystemExit(main())
