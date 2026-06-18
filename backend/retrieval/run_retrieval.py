"""Batch runner for Phase 4 hybrid retrieval outputs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from backend.config.settings import get_settings
from backend.retrieval.hybrid_retrieval import HybridLegalRetriever

LOGGER = logging.getLogger(__name__)

DEFAULT_INPUT_NAME = "test_questions_analyzed.parquet"
DEFAULT_OUTPUT_NAME = "retrieval_results.jsonl"
REQUIRED_COLUMNS = {"id", "question"}


def run_retrieval_batch(
    input_path: str | Path = "data/processed/test_questions_analyzed.parquet",
    output_path: str | Path = "data/outputs/retrieval_results.jsonl",
    *,
    limit: int | None = None,
    start: int = 0,
    top_k: int = 10,
    max_articles: int | None = None,
    min_score: float | None = None,
) -> dict[str, Any]:
    """Run hybrid retrieval for analyzed test questions and write JSONL rows.

    This function only produces retrieval artifacts. It does not generate
    answers, submission citations, `results.json`, or `submission.zip`.
    """

    source_path = _resolve_input_path(input_path)
    target_path = _resolve_output_path(output_path)
    questions_df = _load_questions(source_path)
    batch_df = _slice_questions(questions_df, start=start, limit=limit)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    retriever = HybridLegalRetriever()
    total = batch_df.height
    success_count = 0
    failed_count = 0
    selected_total = 0

    LOGGER.info("Running retrieval: total=%s input=%s output=%s", total, source_path, target_path)

    with target_path.open("w", encoding="utf-8") as output_file:
        for index, row in enumerate(batch_df.iter_rows(named=True), start=1):
            try:
                question_id = _coerce_question_id(row.get("id"))
                question = _coerce_question_text(row.get("question"))
                LOGGER.info("Retrieving question %s/%s: id=%s", index, total, question_id)
                result = retriever.retrieve(
                    question,
                    answer_type=_optional_text(row.get("answer_type")),
                    complexity=_optional_text(row.get("complexity")),
                    top_k=top_k,
                    max_articles=max_articles,
                    min_score=min_score,
                )
            except Exception as exc:
                failed_count += 1
                question_id = row.get("id")
                question = str(row.get("question") or "").strip()
                LOGGER.exception("Retrieval failed for question id=%s", question_id)
                _write_jsonl_row(
                    output_file,
                    {
                        "id": question_id,
                        "question": question,
                        "selected_articles": [],
                        "candidate_count": 0,
                        "debug": {"stage_counts": {}, "errors": {"batch": str(exc)}},
                        "error": str(exc),
                    },
                )
                continue

            selected_articles = list(result.selected_article_ids)
            selected_total += len(selected_articles)
            success_count += 1
            _write_jsonl_row(
                output_file,
                {
                    "id": question_id,
                    "question": question,
                    "selected_articles": selected_articles,
                    "candidate_count": len(result.candidates),
                    "debug": {
                        "stage_counts": result.debug.get("stage_counts", {}),
                        "errors": result.debug.get("errors", {}),
                    },
                },
            )

    avg_selected = (selected_total / success_count) if success_count else 0.0
    summary = {
        "input_path": str(source_path),
        "output_path": str(target_path),
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "avg_selected_articles": avg_selected,
    }
    LOGGER.info(
        "Retrieval complete: total=%s success=%s failed=%s avg_selected_articles=%.2f output=%s",
        total,
        success_count,
        failed_count,
        avg_selected,
        target_path,
    )
    return summary


def _resolve_input_path(path: str | Path) -> Path:
    value = Path(path)
    if str(path) == "data/processed/test_questions_analyzed.parquet":
        return get_settings().paths.processed_dir / DEFAULT_INPUT_NAME
    return value


def _resolve_output_path(path: str | Path) -> Path:
    value = Path(path)
    if str(path) == "data/outputs/retrieval_results.jsonl":
        return get_settings().paths.output_dir / DEFAULT_OUTPUT_NAME
    return value


def _load_questions(input_path: Path) -> pl.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Analyzed questions parquet not found: {input_path}")

    questions_df = pl.read_parquet(input_path)
    missing_columns = REQUIRED_COLUMNS.difference(questions_df.columns)
    if missing_columns:
        raise ValueError(f"Question DataFrame missing required columns: {sorted(missing_columns)}")
    if questions_df.height == 0:
        raise ValueError("Question DataFrame must not be empty")
    return questions_df


def _slice_questions(questions_df: pl.DataFrame, *, start: int, limit: int | None) -> pl.DataFrame:
    if start < 0:
        raise ValueError("start must be >= 0")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0 when provided")
    if limit is None:
        return questions_df.slice(start)
    return questions_df.slice(start, limit)


def _coerce_question_id(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Invalid question id: {value!r}")
    return int(value)


def _coerce_question_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Question must be a string: {value!r}")
    question = value.strip()
    if not question:
        raise ValueError("Question must not be empty")
    return question


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _write_jsonl_row(output_file: Any, row: dict[str, Any]) -> None:
    output_file.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
    output_file.write("\n")
