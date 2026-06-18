"""Thin entrypoint for Phase 5 results.json building."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.settings import get_settings
from backend.submission.build_results import build_results

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    results = build_submission_file(input_path=args.input, output_path=args.output)
    logger.info("Wrote %d submission items to %s", len(results), args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Build final results.json from generated answers.")
    parser.add_argument("--input", default=str(settings.paths.output_dir / "generated_answers.jsonl"))
    parser.add_argument("--output", default=str(settings.paths.output_dir / "results.json"))
    parser.add_argument("--log-level", default="INFO")
    return parser


def build_submission_file(input_path: str | Path, output_path: str | Path) -> list[dict[str, Any]]:
    records = _read_jsonl_records(input_path)
    results = build_results(records)

    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def _read_jsonl_records(input_path: str | Path) -> list[dict[str, Any]]:
    source_path = Path(input_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"generated answers file does not exist: {source_path}")

    records: list[dict[str, Any]] = []
    with source_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(loaded, dict):
                raise ValueError(f"JSONL line {line_number} must be an object")
            records.append(loaded)
    return records


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
