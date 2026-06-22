"""Regenerate QA answers for a selected subset of retrieval records.

This module scans existing retrieval JSONL and only generates answers for IDs
provided by an evaluation report. It does not retrieve, re-rank, select, or
modify submission fields.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from backend.qa.answer_generator import AnswerGenerator
from backend.qa.answer_templates import build_answer_prompt
from backend.qa.article_context_loader import load_selected_article_contexts
from backend.qa.citation_postprocess import postprocess_citations

logger = logging.getLogger(__name__)


def read_unsupported_question_ids(report_path: str | Path) -> list[str]:
    """Read unique question IDs from unsupported_citations_report.csv."""
    path = Path(report_path)
    if not path.is_file():
        raise FileNotFoundError(f"unsupported citation report does not exist: {path}")

    question_ids: list[str] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if "id" not in (reader.fieldnames or []):
            raise ValueError(f"unsupported citation report missing required id column: {path}")

        for row_number, row in enumerate(reader, start=2):
            question_id = _safe_text(row.get("id"))
            if not question_id:
                logger.warning("Skip unsupported report row %d because id is empty", row_number)
                continue
            if question_id in seen:
                continue
            seen.add(question_id)
            question_ids.append(question_id)

    return question_ids


def read_question_ids_csv(ids_csv_path: str | Path, id_column: str = "id") -> list[str]:
    """Read unique question IDs from a CSV file using the configured ID column."""
    path = Path(ids_csv_path)
    column = _safe_text(id_column) or "id"
    if not path.is_file():
        raise FileNotFoundError(f"ids CSV does not exist: {path}")

    question_ids: list[str] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if column not in (reader.fieldnames or []):
            raise ValueError(f"ids CSV missing required {column} column: {path}")

        for row_number, row in enumerate(reader, start=2):
            question_id = _safe_text(row.get(column))
            if not question_id:
                logger.warning("Skip ids CSV row %d because %s is empty", row_number, column)
                continue
            if question_id in seen:
                continue
            seen.add(question_id)
            question_ids.append(question_id)

    return question_ids


def generate_answer_ids_subset(
    ids_csv_path: str | Path,
    retrieval_results_path: str | Path,
    output_path: str | Path,
    legal_articles_path: str | Path,
    generator: AnswerGenerator,
    id_column: str = "id",
    max_tokens: int = 128,
    max_article_chars: int = 700,
    max_total_context_chars: int = 2500,
) -> dict[str, Any]:
    """Regenerate answers for arbitrary IDs read from CSV and write a summary next to output."""
    question_ids = read_question_ids_csv(ids_csv_path, id_column=id_column)
    summary = generate_answers_for_subset(
        retrieval_results_path=retrieval_results_path,
        output_path=output_path,
        question_ids=question_ids,
        legal_articles_path=legal_articles_path,
        generator=generator,
        max_tokens=max_tokens,
        max_article_chars=max_article_chars,
        max_total_context_chars=max_total_context_chars,
    )
    summary.update(
        {
            "ids_csv_path": str(ids_csv_path),
            "retrieval_results_path": str(retrieval_results_path),
            "output_path": str(output_path),
            "max_total_context_chars": max_total_context_chars,
            "max_article_chars": max_article_chars,
            "max_tokens": max_tokens,
        }
    )
    summary_path = Path(output_path).parent / "regeneration_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def generate_answers_for_subset(
    retrieval_results_path: str | Path,
    output_path: str | Path,
    question_ids: list[str],
    legal_articles_path: str | Path,
    generator: AnswerGenerator,
    max_tokens: int = 128,
    max_article_chars: int = 700,
    max_total_context_chars: int = 2500,
) -> dict[str, Any]:
    """Generate answers only for requested question IDs and write a subset JSONL."""
    source_path = Path(retrieval_results_path)
    target_path = Path(output_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"retrieval results file does not exist: {source_path}")

    requested_ids = _deduplicate_ids(question_ids)
    requested_set = set(requested_ids)
    if not requested_ids:
        raise ValueError("question_ids must not be empty")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    processed_ids: list[str] = []

    with source_path.open("r", encoding="utf-8") as source, target_path.open("w", encoding="utf-8") as target:
        for line_number, line in enumerate(source, start=1):
            record = _load_jsonl_record(line, line_number)
            record_id = _safe_text(record.get("id"))
            if record_id not in requested_set:
                continue

            selected_article_ids = _extract_selected_article_ids(record)
            selected_articles = load_selected_article_contexts(
                selected_article_ids,
                legal_articles_path=legal_articles_path,
                max_article_chars=max_article_chars,
                max_total_context_chars=max_total_context_chars,
            )
            question = _safe_text(record.get("question"))
            answer_type = _safe_text(record.get("answer_type")) or "general"
            prompt_preview = build_answer_prompt(
                question=question,
                articles=selected_articles,
                answer_type=answer_type,
            )
            logger.info(
                "Regenerating subset answer id=%s selected_articles=%d hydrated_articles=%d "
                "max_total_context_chars=%s max_article_chars=%s max_tokens=%s "
                "total_context_chars=%d allowed_citation_count=%d prompt_chars=%d",
                record_id,
                len(selected_article_ids),
                len(selected_articles),
                max_total_context_chars,
                max_article_chars,
                max_tokens,
                _count_article_text_chars(selected_articles),
                len(selected_articles),
                len(prompt_preview),
            )

            answer = generator.generate_answer(
                question=question,
                selected_articles=selected_articles,
                answer_type=answer_type,
                max_tokens=max_tokens,
            )
            answer = postprocess_citations(answer, selected_articles)
            output_record = {
                "id": record.get("id"),
                "question": record.get("question"),
                "answer": answer,
                "selected_articles": selected_articles,
            }
            target.write(json.dumps(output_record, ensure_ascii=False) + "\n")
            processed_ids.append(record_id)

    missing_ids = [question_id for question_id in requested_ids if question_id not in set(processed_ids)]
    if missing_ids:
        logger.warning("Missing %d requested IDs in retrieval results", len(missing_ids))

    return {
        "requested": len(requested_ids),
        "processed": len(processed_ids),
        "missing": len(missing_ids),
        "missing_ids": missing_ids,
        "output_path": str(target_path),
    }


def generate_unsupported_citation_subset(
    unsupported_report_path: str | Path,
    retrieval_results_path: str | Path,
    output_path: str | Path,
    legal_articles_path: str | Path,
    generator: AnswerGenerator,
    max_tokens: int = 128,
    max_article_chars: int = 700,
    max_total_context_chars: int = 2500,
) -> dict[str, Any]:
    """Read unsupported IDs from CSV and regenerate only those QA answers."""
    question_ids = read_unsupported_question_ids(unsupported_report_path)
    summary = generate_answers_for_subset(
        retrieval_results_path=retrieval_results_path,
        output_path=output_path,
        question_ids=question_ids,
        legal_articles_path=legal_articles_path,
        generator=generator,
        max_tokens=max_tokens,
        max_article_chars=max_article_chars,
        max_total_context_chars=max_total_context_chars,
    )
    summary["unsupported_report_path"] = str(unsupported_report_path)
    return summary


def _deduplicate_ids(question_ids: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in question_ids:
        question_id = _safe_text(value)
        if not question_id or question_id in seen:
            continue
        seen.add(question_id)
        result.append(question_id)
    return result


def _load_jsonl_record(line: str, line_number: int) -> dict[str, Any]:
    try:
        loaded = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError(f"JSONL line {line_number} must be an object")
    return loaded


def _extract_selected_article_ids(record: dict[str, Any]) -> list[str]:
    selected_articles = record.get("selected_articles")
    if selected_articles is None:
        selected_articles = record.get("selected_article_ids", [])

    if not isinstance(selected_articles, list):
        raise ValueError("selected_articles must be a list")

    article_ids: list[str] = []
    for article in selected_articles:
        if isinstance(article, str):
            article_ids.append(article)
        elif isinstance(article, dict) and article.get("article_id"):
            article_ids.append(str(article["article_id"]))
    return article_ids


def _count_article_text_chars(articles: list[dict[str, Any]]) -> int:
    return sum(len(str(article.get("article_text") or "")) for article in articles if isinstance(article, dict))


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
