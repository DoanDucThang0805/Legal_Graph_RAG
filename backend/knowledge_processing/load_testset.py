"""Loader for the local competition testset."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import ValidationError

from backend.config.settings import get_settings
from backend.knowledge_processing.hf_loader import save_parquet
from backend.knowledge_processing.normalize_text import normalize_vietnamese_text
from backend.schema.question import TestQuestion

logger = logging.getLogger(__name__)


def load_test_questions(
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> pl.DataFrame:
    """Load, validate, normalize, and save competition test questions."""

    settings = get_settings()
    source_path = Path(input_path) if input_path is not None else settings.paths.raw_dir / "R2AIStage1DATA.json"
    target_path = (
        Path(output_path)
        if output_path is not None
        else settings.paths.processed_dir / "test_questions.parquet"
    )

    raw_items = _read_json_list(source_path)
    questions = _validate_questions(raw_items)
    df = pl.DataFrame(
        [question.model_dump() for question in questions],
        schema={"id": pl.Int64, "question": pl.Utf8},
    )
    save_parquet(df, target_path)
    logger.info("Loaded test questions: rows=%s output=%s", df.height, target_path)
    return df


def _read_json_list(input_path: Path) -> list[Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Testset file not found: {input_path}")

    try:
        with input_path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        logger.exception("Invalid JSON testset: path=%s", input_path)
        raise ValueError(f"Invalid JSON testset: {input_path}") from exc

    if not isinstance(data, list):
        logger.error("Testset JSON root must be a list: path=%s type=%s", input_path, type(data).__name__)
        raise ValueError("Testset JSON root must be a list")

    return data


def _validate_questions(raw_items: list[Any]) -> list[TestQuestion]:
    questions: list[TestQuestion] = []
    seen_ids: set[int] = set()
    errors: list[str] = []

    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            errors.append(f"row={index}: item must be an object")
            continue

        try:
            question_id = _coerce_question_id(item.get("id"))
            question_text = normalize_vietnamese_text(item.get("question"))
            question = TestQuestion(id=question_id, question=question_text)
        except (TypeError, ValueError, ValidationError) as exc:
            errors.append(f"row={index}: {exc}")
            continue

        if question.id in seen_ids:
            errors.append(f"row={index}: duplicate id={question.id}")
            continue

        seen_ids.add(question.id)
        questions.append(question)

    if errors:
        for error in errors[:20]:
            logger.error("Invalid testset row: %s", error)
        if len(errors) > 20:
            logger.error("Additional invalid testset rows omitted from log: count=%s", len(errors) - 20)
        raise ValueError(f"Invalid testset rows: {len(errors)}")

    return questions


def _coerce_question_id(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("id must be an integer")

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"id must be convertible to int: {value!r}") from exc
