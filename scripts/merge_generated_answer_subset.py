"""Merge regenerated subset answers into a generated answer JSONL copy."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.settings import get_settings
from backend.evaluation.generated_answer_merge import merge_generated_answer_subset

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    summary = merge_generated_answer_subset(
        base_path=args.base,
        subset_path=args.subset,
        output_path=args.output,
    )
    logger.info("Summary: %s", summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    output_dir = get_settings().paths.output_dir
    parser = argparse.ArgumentParser(description="Merge regenerated answer subset into a baseline JSONL copy.")
    parser.add_argument("--base", default=str(output_dir / "generated_answers_v2_merged.jsonl"))
    parser.add_argument("--subset", default=str(output_dir / "generated_answers_v2_p6r4_subset_unsupported.jsonl"))
    parser.add_argument("--output", default=str(output_dir / "generated_answers_v2_p6r4_merged_for_eval.jsonl"))
    parser.add_argument("--log-level", default="INFO")
    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
