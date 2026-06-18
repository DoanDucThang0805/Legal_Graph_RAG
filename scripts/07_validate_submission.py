"""Thin entrypoint for Phase 5 submission validation."""

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
from backend.submission.make_zip import make_submission_zip
from backend.submission.validate_results import validate_results_file

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    report = validate_results_file(args.input)
    logger.info("Validated %d items", report.num_items)

    for warning in report.warnings:
        logger.warning(warning)
    for error in report.errors:
        logger.error(error)

    if not report.is_valid:
        return 1

    if args.zip_path:
        zip_path = make_submission_zip(args.input, args.zip_path)
        logger.info("Wrote submission zip to %s", zip_path)

    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Validate results.json and optionally create submission.zip.")
    parser.add_argument("--input", default=str(settings.paths.output_dir / "results.json"))
    parser.add_argument("--zip-path", default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
