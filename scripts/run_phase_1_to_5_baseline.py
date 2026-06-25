"""Dry-run-first runner for the Phase 1 -> Phase 5 baseline pipeline."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)

PHASE_ORDER = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class BaselineStep:
    """One existing entrypoint command in the baseline pipeline."""

    phase: int
    name: str
    description: str
    command: tuple[str, ...]
    skip_flag: str | None = None
    supports_limit: bool = False


@dataclass(frozen=True)
class RunSummary:
    total_steps: int
    skipped: int
    succeeded: int
    failed: int
    dry_run: bool


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    repo_root = Path(args.cwd).expanduser().resolve()
    dry_run = not args.execute
    steps = build_steps(
        python_bin=args.python_bin,
        skip_index=args.skip_index,
        limit=args.limit if args.limit is not None else args.sample_size,
        index_mode=args.index_mode,
        build_submission_zip=not args.no_zip,
    )
    selected_steps = select_steps(
        steps,
        start_phase=args.start_phase,
        end_phase=args.end_phase,
        only=args.only,
    )

    if dry_run:
        LOGGER.info("Default is dry-run. Use --execute to run commands.")

    summary, exit_code = run_steps(
        selected_steps,
        cwd=repo_root,
        dry_run=dry_run,
        continue_on_error=args.continue_on_error,
    )
    log_summary(summary)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the existing Phase 1 -> Phase 5 baseline entrypoints in order. "
            "Default is dry-run. Use --execute to run commands."
        )
    )
    parser.add_argument("--execute", action="store_true", help="Actually execute commands. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Kept for explicitness; dry-run is already the default.")
    parser.add_argument("--start-phase", type=int, choices=PHASE_ORDER, default=1)
    parser.add_argument("--end-phase", type=int, choices=PHASE_ORDER, default=5)
    parser.add_argument(
        "--only",
        type=parse_phase_list,
        default=None,
        help="Comma-separated phase ids to run, for example: 1,3,5.",
    )
    parser.add_argument("--skip-index", action="store_true", help="Skip Phase 2 index build step.")
    parser.add_argument(
        "--skip-existing-index",
        action="store_true",
        dest="skip_index",
        help="Alias for --skip-index.",
    )
    parser.add_argument(
        "--index-mode",
        choices=("all-no-dense", "bm25", "exact", "dense", "vector"),
        default="all-no-dense",
        help="Phase 2 --only value. Defaults to all-no-dense to avoid accidental dense builds.",
    )
    parser.add_argument("--sample-size", type=positive_int, default=None, help="Alias for --limit on supported child scripts.")
    parser.add_argument("--limit", type=positive_int, default=None, help="Limit rows on supported child scripts.")
    parser.add_argument("--python-bin", default=sys.executable, help="Python executable used for child commands.")
    parser.add_argument("--cwd", default=".", help="Repository root used as subprocess working directory.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue after failures instead of stopping.")
    parser.add_argument("--no-zip", action="store_true", help="Do not ask validation step to create submission.zip.")
    parser.add_argument("--log-level", default="INFO")
    return parser


def build_steps(
    *,
    python_bin: str,
    skip_index: bool,
    limit: int | None,
    index_mode: str,
    build_submission_zip: bool,
) -> list[BaselineStep]:
    steps = [
        BaselineStep(
            phase=1,
            name="Phase 1",
            description="Build canonical corpus",
            command=(python_bin, "scripts/01_build_corpus.py"),
        ),
        BaselineStep(
            phase=2,
            name="Phase 2",
            description=f"Build indexes ({index_mode})",
            command=(python_bin, "scripts/02_build_indexes.py", "--only", index_mode),
            skip_flag="--skip-index",
        ),
        BaselineStep(
            phase=3,
            name="Phase 3",
            description="Analyze questions",
            command=(python_bin, "scripts/03_analyze_questions.py"),
        ),
        BaselineStep(
            phase=4,
            name="Phase 4",
            description="Run hybrid retrieval",
            command=(python_bin, "scripts/04_run_retrieval.py"),
            supports_limit=True,
        ),
        BaselineStep(
            phase=5,
            name="Phase 5A",
            description="Generate answers",
            command=(python_bin, "scripts/05_generate_answers.py"),
            supports_limit=True,
        ),
        BaselineStep(
            phase=5,
            name="Phase 5B",
            description="Build submission results",
            command=(python_bin, "scripts/06_build_submission.py"),
        ),
        BaselineStep(
            phase=5,
            name="Phase 5C",
            description="Validate submission",
            command=_validation_command(python_bin, build_submission_zip),
        ),
    ]

    prepared_steps: list[BaselineStep] = []
    for step in steps:
        if skip_index and step.skip_flag == "--skip-index":
            prepared_steps.append(step)
            continue

        command = step.command
        if limit is not None and step.supports_limit:
            command = (*command, "--limit", str(limit))
        prepared_steps.append(
            BaselineStep(
                phase=step.phase,
                name=step.name,
                description=step.description,
                command=command,
                skip_flag=step.skip_flag if skip_index else None,
                supports_limit=step.supports_limit,
            )
        )
    return prepared_steps


def select_steps(
    steps: Sequence[BaselineStep],
    *,
    start_phase: int,
    end_phase: int,
    only: set[int] | None,
) -> list[BaselineStep]:
    if start_phase > end_phase:
        raise ValueError("--start-phase must be less than or equal to --end-phase")

    selected: list[BaselineStep] = []
    for step in steps:
        if only is not None and step.phase not in only:
            continue
        if only is None and not (start_phase <= step.phase <= end_phase):
            continue
        selected.append(step)
    return selected


def run_steps(
    steps: Sequence[BaselineStep],
    *,
    cwd: Path,
    dry_run: bool,
    continue_on_error: bool,
) -> tuple[RunSummary, int]:
    succeeded = 0
    failed = 0
    skipped = 0
    exit_code = 0

    for step in steps:
        if step.skip_flag:
            skipped += 1
            LOGGER.info("[SKIP] %s - %s (%s)", step.name, step.description, step.skip_flag)
            continue

        LOGGER.info("[START] %s - %s", step.name, step.description)
        LOGGER.info("[CMD] %s", format_command(step.command))

        if dry_run:
            succeeded += 1
            LOGGER.info("[OK] %s - dry-run", step.name)
            continue

        completed = subprocess.run(step.command, cwd=cwd, shell=False)
        if completed.returncode == 0:
            succeeded += 1
            LOGGER.info("[OK] %s - %s", step.name, step.description)
            continue

        failed += 1
        exit_code = completed.returncode or 1
        LOGGER.error("[FAIL] %s - exit_code=%s", step.name, completed.returncode)
        if not continue_on_error:
            break

    summary = RunSummary(
        total_steps=len(steps),
        skipped=skipped,
        succeeded=succeeded,
        failed=failed,
        dry_run=dry_run,
    )
    return summary, exit_code


def log_summary(summary: RunSummary) -> None:
    LOGGER.info(
        "[SUMMARY] total=%d skipped=%d succeeded=%d failed=%d dry_run=%s",
        summary.total_steps,
        summary.skipped,
        summary.succeeded,
        summary.failed,
        str(summary.dry_run).lower(),
    )


def format_command(command: Sequence[str]) -> str:
    return " ".join(command)


def parse_phase_list(value: str) -> set[int]:
    phases: set[int] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        phase = int(item)
        if phase not in PHASE_ORDER:
            raise argparse.ArgumentTypeError(f"unsupported phase id: {phase}")
        phases.add(phase)
    if not phases:
        raise argparse.ArgumentTypeError("--only must include at least one phase id")
    return phases


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(message)s",
    )


def _validation_command(python_bin: str, build_submission_zip: bool) -> tuple[str, ...]:
    command = (python_bin, "scripts/07_validate_submission.py")
    if build_submission_zip:
        command = (*command, "--zip-path", "data/outputs/submission.zip")
    return command


if __name__ == "__main__":
    raise SystemExit(main())
