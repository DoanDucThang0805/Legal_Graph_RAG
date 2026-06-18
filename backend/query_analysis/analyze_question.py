"""Orchestrate Phase 3 query analysis for test questions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from backend.config.settings import get_settings
from backend.knowledge_processing.hf_loader import save_parquet
from backend.query_analysis.answer_type_classifier import classify_answer_type
from backend.query_analysis.complexity_detector import detect_complexity
from backend.query_analysis.domain_router import classify_domain
from backend.query_analysis.legal_entity_extractor import extract_legal_entities
from backend.query_analysis.query_expander import expand_query

LOGGER = logging.getLogger(__name__)

REQUIRED_INPUT_COLUMNS = {"id", "question"}


def analyze_test_questions(
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> pl.DataFrame:
    """Read test questions, analyze them, and save the enriched parquet file."""

    settings = get_settings()
    source_path = Path(input_path) if input_path is not None else settings.paths.processed_dir / "test_questions.parquet"
    target_path = (
        Path(output_path)
        if output_path is not None
        else settings.paths.processed_dir / "test_questions_analyzed.parquet"
    )

    questions_df = _read_questions(source_path)
    analyzed_df = analyze_questions_dataframe(questions_df)
    save_parquet(analyzed_df, target_path)
    LOGGER.info("Analyzed test questions: rows=%s output=%s", analyzed_df.height, target_path)
    return analyzed_df


def analyze_questions_dataframe(questions_df: pl.DataFrame) -> pl.DataFrame:
    """Analyze an in-memory questions DataFrame."""

    _validate_questions_dataframe(questions_df)
    rows = [analyze_question_row(row) for row in questions_df.select(["id", "question"]).iter_rows(named=True)]
    return pl.DataFrame(rows, schema=_output_schema())


def analyze_question_row(row: dict[str, Any]) -> dict[str, Any]:
    """Analyze one question row and return a parquet-friendly mapping."""

    question_id = _coerce_question_id(row.get("id"))
    question = _coerce_question_text(row.get("question"))

    domain = classify_domain(question)
    answer_type = classify_answer_type(question)
    complexity = detect_complexity(question, domain_scores=domain.scores)
    legal_entities = extract_legal_entities(question)
    expanded_queries = expand_query(question)

    return {
        "id": question_id,
        "question": question,
        "domain": domain.domain,
        "domain_confidence": domain.confidence,
        "answer_type": answer_type.answer_type,
        "answer_type_confidence": answer_type.confidence,
        "complexity": complexity.complexity,
        "complexity_score": complexity.score,
        "legal_entities_json": _to_json_string(legal_entities),
        "expanded_queries_json": _to_json_string(expanded_queries),
    }


def _read_questions(input_path: Path) -> pl.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Question parquet not found: {input_path}")

    try:
        return pl.read_parquet(input_path)
    except Exception as exc:
        LOGGER.exception("Failed to read question parquet: path=%s", input_path)
        raise RuntimeError(f"Failed to read question parquet: {input_path}") from exc


def _validate_questions_dataframe(questions_df: pl.DataFrame) -> None:
    missing_columns = REQUIRED_INPUT_COLUMNS.difference(questions_df.columns)
    if missing_columns:
        raise ValueError(f"Question DataFrame missing required columns: {sorted(missing_columns)}")

    if questions_df.height == 0:
        raise ValueError("Question DataFrame must not be empty")

    null_counts = questions_df.select([pl.col("id").null_count(), pl.col("question").null_count()]).row(0)
    if any(count > 0 for count in null_counts):
        raise ValueError("Question DataFrame must not contain null id/question values")


def _coerce_question_id(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Invalid question id: {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Question id must be convertible to int: {value!r}") from exc


def _coerce_question_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Question must be a string: {value!r}")
    question = value.strip()
    if not question:
        raise ValueError("Question must not be empty")
    return question


def _to_json_string(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _output_schema() -> dict[str, pl.DataType]:
    return {
        "id": pl.Int64,
        "question": pl.Utf8,
        "domain": pl.Utf8,
        "domain_confidence": pl.Float64,
        "answer_type": pl.Utf8,
        "answer_type_confidence": pl.Float64,
        "complexity": pl.Utf8,
        "complexity_score": pl.Float64,
        "legal_entities_json": pl.Utf8,
        "expanded_queries_json": pl.Utf8,
    }
