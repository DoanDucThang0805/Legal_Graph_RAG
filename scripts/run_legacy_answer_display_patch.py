"""Run P6.R8 targeted legacy answer display patch."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.evaluation.legacy_answer_display_patch import run_legacy_answer_display_patch

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    summary = run_legacy_answer_display_patch(
        p6r7_report_path=args.p6r7_report,
        answers_path=args.answers,
        output_dir=args.output_dir,
    )
    logger.info("Summary: %s", summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Patch display-only Khong so fragments in target generated answers.")
    parser.add_argument("--p6r7-report", required=True)
    parser.add_argument("--answers", required=True)
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
