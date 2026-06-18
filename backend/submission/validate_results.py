"""Validation helpers for competition results.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ARTICLE_NO_PATTERN = re.compile(r"\b(?:điều|Điều)\s+0*(\d+[a-zA-Z]?)\b", flags=re.IGNORECASE)
REQUIRED_FIELDS = {"id", "question", "answer", "relevant_docs", "relevant_articles"}


@dataclass
class ValidationReport:
    """Structured validation result for submission files/items."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    num_items: int = 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def validate_results_file(path: str | Path, expected_ids: set[int] | list[int] | None = None) -> ValidationReport:
    """Load and validate a results.json file."""

    report = ValidationReport()
    results_path = Path(path)

    try:
        with results_path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
    except FileNotFoundError:
        report.add_error(f"results file does not exist: {results_path}")
        return report
    except json.JSONDecodeError as exc:
        report.add_error(f"results file is not valid JSON: {exc}")
        return report

    return validate_results_items(loaded, expected_ids=expected_ids)


def validate_results_items(items: Any, expected_ids: set[int] | list[int] | None = None) -> ValidationReport:
    """Validate results.json items."""

    report = ValidationReport()
    if not isinstance(items, list):
        report.add_error("results root must be a list")
        return report

    report.num_items = len(items)
    seen_ids: set[int] = set()

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            report.add_error(f"item {index} must be an object")
            continue

        _validate_required_fields(item, index, report)
        _validate_id(item, index, seen_ids, report)
        _validate_required_text(item, index, "question", report)
        _validate_required_text(item, index, "answer", report)
        _validate_citation_lists(item, index, report)

    _validate_expected_ids(seen_ids, expected_ids, report)
    return report


def _validate_required_fields(item: dict[str, Any], index: int, report: ValidationReport) -> None:
    missing_fields = sorted(REQUIRED_FIELDS.difference(item))
    for field_name in missing_fields:
        report.add_error(f"item {index} missing required field: {field_name}")


def _validate_id(item: dict[str, Any], index: int, seen_ids: set[int], report: ValidationReport) -> None:
    item_id = item.get("id")
    if not isinstance(item_id, int):
        report.add_error(f"item {index} id must be an integer")
        return

    if item_id in seen_ids:
        report.add_error(f"duplicate id: {item_id}")
        return

    seen_ids.add(item_id)


def _validate_required_text(
    item: dict[str, Any],
    index: int,
    field_name: str,
    report: ValidationReport,
) -> None:
    value = item.get(field_name)
    if not isinstance(value, str) or not value.strip():
        report.add_error(f"item {index} {field_name} must be a non-empty string")


def _validate_citation_lists(item: dict[str, Any], index: int, report: ValidationReport) -> None:
    relevant_docs = item.get("relevant_docs")
    relevant_articles = item.get("relevant_articles")

    if not _is_string_list(relevant_docs):
        report.add_error(f"item {index} relevant_docs must be a list of strings")
        return

    if not _is_string_list(relevant_articles):
        report.add_error(f"item {index} relevant_articles must be a list of strings")
        return

    parsed_articles = _parse_relevant_articles(relevant_articles, index, report)
    _validate_docs_derived_from_articles(relevant_docs, parsed_articles, index, report)
    _validate_answer_mentions_article(item.get("answer"), parsed_articles, index, report)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _parse_relevant_articles(
    relevant_articles: list[str],
    index: int,
    report: ValidationReport,
) -> list[tuple[str, str, str]]:
    parsed_articles: list[tuple[str, str, str]] = []
    for article in relevant_articles:
        parts = [part.strip() for part in article.split("|", maxsplit=2)]
        if len(parts) != 3 or not all(parts):
            report.add_error(f"item {index} relevant_article has invalid canonical format: {article}")
            continue
        parsed_articles.append((parts[0], parts[1], parts[2]))
    return parsed_articles


def _validate_docs_derived_from_articles(
    relevant_docs: list[str],
    parsed_articles: list[tuple[str, str, str]],
    index: int,
    report: ValidationReport,
) -> None:
    article_law_ids = {law_id for law_id, _, _ in parsed_articles}

    for doc in relevant_docs:
        doc_law_id = doc.split("|", maxsplit=1)[0].strip()
        if doc_law_id not in article_law_ids:
            report.add_error(f"item {index} relevant_doc is not derived from relevant_articles: {doc}")


def _validate_answer_mentions_article(
    answer: Any,
    parsed_articles: list[tuple[str, str, str]],
    index: int,
    report: ValidationReport,
) -> None:
    if not parsed_articles or not isinstance(answer, str):
        return

    normalized_answer = _normalize_article_mentions(answer).casefold()
    article_nos = [_normalize_article_mentions(article_no).casefold() for _, _, article_no in parsed_articles]
    if not any(article_no in normalized_answer for article_no in article_nos):
        report.add_error(f"item {index} answer does not mention any selected article_no")


def _validate_expected_ids(
    seen_ids: set[int],
    expected_ids: set[int] | list[int] | None,
    report: ValidationReport,
) -> None:
    if expected_ids is None:
        return

    expected_set = set(expected_ids)
    missing_ids = sorted(expected_set.difference(seen_ids))
    for item_id in missing_ids:
        report.add_error(f"missing expected id: {item_id}")


def _normalize_article_mentions(text: str) -> str:
    return ARTICLE_NO_PATTERN.sub(lambda match: f"Điều {match.group(1)}", text)
