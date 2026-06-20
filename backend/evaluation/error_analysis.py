"""Build descriptive error analysis reports for retrieval and QA outputs."""

from __future__ import annotations

import csv
import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.evaluation.unsupported_citations import (
    UnsupportedCitation,
    detect_unsupported_citations,
    format_unsupported_citation,
)


logger = logging.getLogger(__name__)

LOW_CONFIDENCE_FILENAME = "low_confidence_questions.csv"
RETRIEVAL_DEBUG_FILENAME = "retrieval_debug_report.csv"
UNSUPPORTED_CITATIONS_FILENAME = "unsupported_citations_report.csv"

LOW_CANDIDATE_THRESHOLD = 5
ANSWER_TOO_SHORT_THRESHOLD = 80
PREVIEW_LENGTH = 300

LEGAL_REFERENCE_RE = re.compile(
    r"(điều\s+\d+[a-z]?|\d+/\d+/(?:qh|nđ|nd|tt|qđ|qd))",
    flags=re.IGNORECASE,
)
INSUFFICIENT_BASIS_PHRASES = (
    "không đủ căn cứ",
    "chưa đủ căn cứ",
    "không có đủ căn cứ",
    "không thể kết luận chắc chắn",
)
TRUNCATED_SUFFIXES = (",", "(", "[", "{", ":", "Điều", "điều", "khoản")
UNKNOWN_LAW_IDS = {"", "none", "null", "không số", "khong so", "không rõ", "unknown"}


def build_error_analysis_report(
    retrieval_results_path: str,
    generated_answers_path: str,
    output_dir: str,
) -> dict[str, Any]:
    """Create low-confidence, retrieval debug, and unsupported citation reports.

    This function only analyzes existing JSONL outputs. It does not call
    retrieval, QA generation, submission builders, or any LLM component.
    """
    retrieval_records = _read_jsonl_by_id(Path(retrieval_results_path))
    answer_records = _read_jsonl_by_id(Path(generated_answers_path))
    ordered_ids = _merge_ordered_ids(retrieval_records, answer_records)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    low_confidence_path = output_path / LOW_CONFIDENCE_FILENAME
    retrieval_debug_path = output_path / RETRIEVAL_DEBUG_FILENAME
    unsupported_citations_path = output_path / UNSUPPORTED_CITATIONS_FILENAME

    low_confidence_rows: list[dict[str, Any]] = []
    debug_rows: list[dict[str, Any]] = []
    unsupported_citation_rows: list[dict[str, Any]] = []

    for record_id in ordered_ids:
        retrieval_record = retrieval_records.get(record_id, {})
        answer_record = answer_records.get(record_id, {})
        combined = _combine_records(record_id, retrieval_record, answer_record)
        issue_categories, reasons = _detect_issue_categories(combined)

        debug_rows.append(_build_debug_row(combined))
        unsupported_citations = _safe_list(combined.get("unsupported_citations"))
        if unsupported_citations:
            unsupported_citation_rows.append(_build_unsupported_citation_row(combined, unsupported_citations))
        if issue_categories:
            low_confidence_rows.append(
                _build_low_confidence_row(combined, issue_categories, reasons)
            )

    _write_csv(low_confidence_path, _low_confidence_columns(), low_confidence_rows)
    _write_csv(retrieval_debug_path, _debug_columns(), debug_rows)
    _write_csv(unsupported_citations_path, _unsupported_citation_columns(), unsupported_citation_rows)

    return {
        "total_questions": len(ordered_ids),
        "low_confidence_count": len(low_confidence_rows),
        "unsupported_citation_count": len(unsupported_citation_rows),
        "low_confidence_path": str(low_confidence_path),
        "retrieval_debug_report_path": str(retrieval_debug_path),
        "unsupported_citations_report_path": str(unsupported_citations_path),
    }


def _read_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        logger.warning("JSONL input does not exist: %s", path)
        return records

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skip invalid JSONL line %s in %s: %s", line_number, path, exc)
                continue

            if not isinstance(value, dict):
                logger.warning("Skip non-object JSONL line %s in %s", line_number, path)
                continue

            record_id = _safe_id(value.get("id"))
            if record_id is None:
                logger.warning("Skip JSONL line %s in %s because id is missing", line_number, path)
                continue

            records[record_id] = value

    return records


def _merge_ordered_ids(
    retrieval_records: Mapping[str, dict[str, Any]],
    answer_records: Mapping[str, dict[str, Any]],
) -> list[str]:
    ordered_ids = list(retrieval_records)
    seen = set(ordered_ids)
    for record_id in answer_records:
        if record_id not in seen:
            ordered_ids.append(record_id)
            seen.add(record_id)
    return ordered_ids


def _combine_records(
    record_id: str,
    retrieval_record: Mapping[str, Any],
    answer_record: Mapping[str, Any],
) -> dict[str, Any]:
    retrieval_selected = _safe_list(retrieval_record.get("selected_articles"))
    answer_selected = _safe_list(answer_record.get("selected_articles"))
    selected_source = answer_selected if answer_selected else retrieval_selected
    debug = _safe_dict(retrieval_record.get("debug"))
    stage_counts = _safe_dict(debug.get("stage_counts"))
    errors = _safe_dict(debug.get("errors"))
    answer = _safe_text(answer_record.get("answer"))

    return {
        "id": record_id,
        "question": _first_text(retrieval_record.get("question"), answer_record.get("question")),
        "answer": answer,
        "selected_articles": selected_source,
        "retrieval_selected_articles": retrieval_selected,
        "answer_selected_articles": answer_selected,
        "unsupported_citations": detect_unsupported_citations(answer, selected_source),
        "candidate_count": _safe_int(retrieval_record.get("candidate_count")),
        "stage_counts": stage_counts,
        "errors": errors,
    }


def _detect_issue_categories(record: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    reasons: list[str] = []
    selected_count = len(_article_ids(record.get("selected_articles")))
    candidate_count = _candidate_count(record)
    answer = _safe_text(record.get("answer"))
    stage_counts = _safe_dict(record.get("stage_counts"))
    exact_count = _safe_int(stage_counts.get("exact"))

    def add_issue(category: str, reason: str) -> None:
        issues.append(category)
        reasons.append(reason)

    if selected_count == 0:
        add_issue("no_selected_articles", "không có điều luật được chọn")
    elif selected_count <= 2:
        add_issue("too_few_selected_articles", "số điều luật được chọn quá ít")

    if selected_count >= 10:
        add_issue("too_many_selected_articles", "số điều luật được chọn quá nhiều")

    if _has_empty_article_text(_safe_list(record.get("answer_selected_articles"))):
        add_issue("empty_article_text", "có điều luật thiếu article_text")

    if not answer:
        add_issue("answer_empty", "answer rỗng")
    elif len(answer) < ANSWER_TOO_SHORT_THRESHOLD:
        add_issue("answer_too_short", "answer quá ngắn")

    if answer and _looks_truncated(answer):
        add_issue("answer_maybe_truncated", "answer có dấu hiệu bị cắt giữa chừng")

    if _has_insufficient_basis(answer):
        add_issue("answer_insufficient_basis", "answer nêu chưa đủ căn cứ")

    if _safe_dict(record.get("errors")):
        add_issue("retrieval_stage_error", "debug.errors không rỗng")

    if candidate_count < LOW_CANDIDATE_THRESHOLD:
        add_issue("low_candidate_count", "candidate_count hoặc fused_candidates thấp")

    question = _safe_text(record.get("question"))
    if LEGAL_REFERENCE_RE.search(question) and exact_count == 0:
        add_issue(
            "exact_missing_for_legal_reference_question",
            "câu hỏi có dấu hiệu tham chiếu pháp lý nhưng exact_count = 0",
        )

    if _has_legacy_or_unknown_law_id(_safe_list(record.get("answer_selected_articles"))):
        add_issue("legacy_or_unknown_law_id", "có selected article thiếu hoặc không rõ law_id")

    if _safe_list(record.get("unsupported_citations")):
        add_issue(
            "unsupported_citation_in_answer",
            "answer viện dẫn điều/văn bản không nằm trong selected_articles",
        )

    return issues, reasons


def _build_low_confidence_row(
    record: Mapping[str, Any],
    issue_categories: list[str],
    reasons: list[str],
) -> dict[str, Any]:
    answer = _safe_text(record.get("answer"))
    selected_articles = _safe_list(record.get("selected_articles"))
    return {
        "id": record.get("id", ""),
        "question": _safe_text(record.get("question")),
        "issue_categories": ";".join(issue_categories),
        "issue_count": len(issue_categories),
        "reason": ";".join(reasons),
        "selected_count": len(_article_ids(selected_articles)),
        "candidate_count": _candidate_count(record),
        "answer_length": len(answer),
        "answer_preview": _preview(answer, PREVIEW_LENGTH),
        "selected_articles_preview": ";".join(_article_ids(selected_articles)[:3]),
    }


def _build_debug_row(record: Mapping[str, Any]) -> dict[str, Any]:
    stage_counts = _safe_dict(record.get("stage_counts"))
    errors = _safe_dict(record.get("errors"))
    return {
        "id": record.get("id", ""),
        "question": _safe_text(record.get("question")),
        "candidate_count": _candidate_count(record),
        "selected_count": len(_article_ids(record.get("selected_articles"))),
        "bm25_legal_count": _safe_int(stage_counts.get("bm25_legal")),
        "dense_legal_count": _safe_int(stage_counts.get("dense_legal")),
        "exact_count": _safe_int(stage_counts.get("exact")),
        "phapdien_mapped_count": _safe_int(stage_counts.get("phapdien_mapped")),
        "fused_candidates_count": _safe_int(stage_counts.get("fused_candidates")),
        "selected_candidates_count": _safe_int(stage_counts.get("selected_candidates")),
        "has_errors": bool(errors),
        "errors": _json_preview(errors),
        "top_selected_articles": ";".join(_article_ids(record.get("selected_articles"))[:5]),
    }


def _build_unsupported_citation_row(
    record: Mapping[str, Any],
    unsupported_citations: list[Any],
) -> dict[str, Any]:
    answer = _safe_text(record.get("answer"))
    selected_articles = _safe_list(record.get("selected_articles"))
    formatted = [
        format_unsupported_citation(citation)
        for citation in unsupported_citations
        if isinstance(citation, UnsupportedCitation)
    ]
    return {
        "id": record.get("id", ""),
        "question": _safe_text(record.get("question")),
        "unsupported_count": len(formatted),
        "unsupported_citations": ";".join(formatted),
        "selected_articles_preview": ";".join(_article_ids(selected_articles)[:3]),
        "answer_preview": _preview(answer, PREVIEW_LENGTH),
    }


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _low_confidence_columns() -> list[str]:
    return [
        "id",
        "question",
        "issue_categories",
        "issue_count",
        "reason",
        "selected_count",
        "candidate_count",
        "answer_length",
        "answer_preview",
        "selected_articles_preview",
    ]


def _debug_columns() -> list[str]:
    return [
        "id",
        "question",
        "candidate_count",
        "selected_count",
        "bm25_legal_count",
        "dense_legal_count",
        "exact_count",
        "phapdien_mapped_count",
        "fused_candidates_count",
        "selected_candidates_count",
        "has_errors",
        "errors",
        "top_selected_articles",
    ]


def _unsupported_citation_columns() -> list[str]:
    return [
        "id",
        "question",
        "unsupported_count",
        "unsupported_citations",
        "selected_articles_preview",
        "answer_preview",
    ]


def _candidate_count(record: Mapping[str, Any]) -> int:
    candidate_count = _safe_int(record.get("candidate_count"))
    if candidate_count:
        return candidate_count
    stage_counts = _safe_dict(record.get("stage_counts"))
    return _safe_int(stage_counts.get("fused_candidates"))


def _has_empty_article_text(articles: list[Any]) -> bool:
    for article in articles:
        if isinstance(article, Mapping):
            if not _safe_text(article.get("article_text")):
                return True
    return False


def _looks_truncated(answer: str) -> bool:
    stripped_answer = answer.strip()
    if not stripped_answer:
        return False

    if stripped_answer.endswith(TRUNCATED_SUFFIXES):
        return True

    # Flag nhẹ các câu có ngoặc mở nhiều hơn ngoặc đóng, thường gặp khi generation bị cắt.
    bracket_pairs = (("(", ")"), ("[", "]"), ("{", "}"))
    return any(stripped_answer.count(opening) > stripped_answer.count(closing) for opening, closing in bracket_pairs)


def _has_insufficient_basis(answer: str) -> bool:
    lowered = answer.lower()
    return any(phrase in lowered for phrase in INSUFFICIENT_BASIS_PHRASES)


def _has_legacy_or_unknown_law_id(articles: list[Any]) -> bool:
    for article in articles:
        if not isinstance(article, Mapping):
            continue

        law_id = _safe_text(article.get("law_id"))
        if law_id.lower() in UNKNOWN_LAW_IDS:
            return True

        # Chỉ flag heuristic rất nhẹ, không loại bỏ citation hay sửa selected_articles.
        if re.search(r"\b(19[0-8]\d)\b", law_id):
            return True

    return False


def _article_ids(articles: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for article in _safe_list(articles):
        if isinstance(article, Mapping):
            value = _first_text(
                article.get("article_id"),
                article.get("legal_article_id"),
                article.get("law_id"),
            )
        else:
            value = _safe_text(article)

        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_id(value: Any) -> str | None:
    text = _safe_text(value)
    return text or None


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return ""


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str):
        try:
            return max(int(float(value.strip())), 0)
        except ValueError:
            return 0
    return 0


def _preview(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    return compact[:limit]


def _json_preview(value: Mapping[str, Any]) -> str:
    if not value:
        return ""
    return _preview(json.dumps(value, ensure_ascii=False, sort_keys=True), PREVIEW_LENGTH)
