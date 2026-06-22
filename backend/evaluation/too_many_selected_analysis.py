"""Analyze too_many_selected_articles cases from Phase 6 error reports.

This module reads existing evaluation artifacts and produces diagnostic reports.
It does not retrieve, select, generate answers, call LLMs, or modify baseline
outputs.
"""

from __future__ import annotations

import csv
import json
import logging
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ISSUE_TOO_MANY_SELECTED = "too_many_selected_articles"
ISSUE_LEGACY_OR_UNKNOWN = "legacy_or_unknown_law_id"
ISSUE_TRUNCATED = "answer_maybe_truncated"
ISSUE_INSUFFICIENT_BASIS = "answer_insufficient_basis"

REPORT_FILENAME = "too_many_selected_articles_report.csv"
SUMMARY_FILENAME = "too_many_selected_articles_summary.json"
LAW_DISTRIBUTION_FILENAME = "too_many_selected_articles_law_distribution.csv"
COUNT_DISTRIBUTION_FILENAME = "too_many_selected_articles_count_distribution.csv"
SAMPLES_FILENAME = "too_many_selected_articles_samples.md"

UNKNOWN_LAW_IDS = {"", "none", "null", "khong so", "không số", "khong ro", "không rõ", "unknown"}
MULTIHOP_QUESTION_SIGNALS = (
    " và ",
    "đồng thời",
    "trường hợp",
    "thủ tục",
    "hồ sơ",
    "điều kiện",
    "xử phạt",
    "mức phạt",
    "nghĩa vụ",
    "trách nhiệm",
)
PREVIEW_LIMIT = 300
LIST_PREVIEW_LIMIT = 8


REPORT_COLUMNS = [
    "id",
    "question",
    "selected_count",
    "unique_law_count",
    "unique_law_ids",
    "unique_law_titles_preview",
    "unique_article_count",
    "selected_article_ids_preview",
    "selected_article_nos_preview",
    "has_legacy_or_unknown_law_id",
    "has_answer_maybe_truncated",
    "has_answer_insufficient_basis",
    "answer_length_chars",
    "answer_preview",
    "heuristic_category",
    "heuristic_reason",
    "recommended_action",
]

LAW_DISTRIBUTION_COLUMNS = ["law_id", "law_title", "case_count", "article_count", "example_ids"]
COUNT_DISTRIBUTION_COLUMNS = ["selected_count", "case_count", "percentage"]


def build_too_many_selected_analysis(
    low_confidence_path: str | Path,
    retrieval_results_path: str | Path,
    output_dir: str | Path,
    generated_answers_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build all P6.R5 too_many_selected_articles diagnostic reports."""
    low_rows = read_low_confidence_rows(low_confidence_path)
    too_many_rows = filter_too_many_selected_rows(low_rows)
    retrieval_records = read_jsonl_by_id(retrieval_results_path)
    answer_records = read_jsonl_by_id(generated_answers_path) if generated_answers_path else {}

    report_rows = [
        build_question_report_row(low_row, retrieval_records.get(_safe_id(low_row.get("id")), {}), answer_records.get(_safe_id(low_row.get("id")), {}))
        for low_row in too_many_rows
    ]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    law_distribution_rows = build_law_distribution(report_rows)
    count_distribution_rows = build_selected_count_distribution(report_rows)
    summary = build_summary(report_rows, law_distribution_rows, count_distribution_rows)

    write_csv(output_path / REPORT_FILENAME, REPORT_COLUMNS, report_rows)
    write_csv(output_path / LAW_DISTRIBUTION_FILENAME, LAW_DISTRIBUTION_COLUMNS, law_distribution_rows)
    write_csv(output_path / COUNT_DISTRIBUTION_FILENAME, COUNT_DISTRIBUTION_COLUMNS, count_distribution_rows)
    write_json(output_path / SUMMARY_FILENAME, summary)
    write_samples_markdown(output_path / SAMPLES_FILENAME, report_rows, summary)

    return {
        **summary,
        "report_path": str(output_path / REPORT_FILENAME),
        "summary_path": str(output_path / SUMMARY_FILENAME),
        "law_distribution_path": str(output_path / LAW_DISTRIBUTION_FILENAME),
        "count_distribution_path": str(output_path / COUNT_DISTRIBUTION_FILENAME),
        "samples_path": str(output_path / SAMPLES_FILENAME),
    }


def read_low_confidence_rows(path: str | Path) -> list[dict[str, str]]:
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"low confidence CSV does not exist: {source_path}")

    with source_path.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def filter_too_many_selected_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if ISSUE_TOO_MANY_SELECTED in split_issue_categories(row.get("issue_categories"))]


def read_jsonl_by_id(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}

    source_path = Path(path)
    if not source_path.is_file():
        logger.warning("JSONL input does not exist: %s", source_path)
        return {}

    records: dict[str, dict[str, Any]] = {}
    with source_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skip invalid JSONL line %d in %s: %s", line_number, source_path, exc)
                continue
            if not isinstance(loaded, dict):
                logger.warning("Skip non-object JSONL line %d in %s", line_number, source_path)
                continue
            record_id = _safe_id(loaded.get("id"))
            if not record_id:
                logger.warning("Skip JSONL line %d in %s because id is missing", line_number, source_path)
                continue
            records[record_id] = loaded
    return records


def build_question_report_row(
    low_row: Mapping[str, Any],
    retrieval_record: Mapping[str, Any],
    answer_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    answer_record = answer_record or {}
    issue_categories = split_issue_categories(low_row.get("issue_categories"))
    selected_articles = _selected_articles(retrieval_record, answer_record)
    article_infos = [_article_info(article) for article in selected_articles]

    article_ids = _dedupe_preserve_order(info["article_id"] for info in article_infos if info["article_id"])
    law_ids = _dedupe_preserve_order(info["law_id"] for info in article_infos if info["law_id"])
    law_titles = _dedupe_preserve_order(info["law_title"] for info in article_infos if info["law_title"])
    article_nos = _dedupe_preserve_order(info["article_no"] for info in article_infos if info["article_no"])
    answer = _first_text(answer_record.get("answer"), low_row.get("answer_preview"))

    selected_count = _safe_int(low_row.get("selected_count")) or len(article_ids) or len(selected_articles)
    has_legacy = ISSUE_LEGACY_OR_UNKNOWN in issue_categories or any(_is_legacy_or_unknown_law_id(law_id) for law_id in law_ids)
    has_truncated = ISSUE_TRUNCATED in issue_categories
    has_insufficient = ISSUE_INSUFFICIENT_BASIS in issue_categories
    heuristic_category, heuristic_reason, recommended_action = classify_case(
        question=_first_text(retrieval_record.get("question"), answer_record.get("question"), low_row.get("question")),
        selected_count=selected_count,
        unique_law_count=len(law_ids),
        has_legacy_or_unknown_law_id=has_legacy,
        has_answer_maybe_truncated=has_truncated,
        has_answer_insufficient_basis=has_insufficient,
    )

    return {
        "id": _safe_id(low_row.get("id")),
        "question": _first_text(retrieval_record.get("question"), answer_record.get("question"), low_row.get("question")),
        "selected_count": selected_count,
        "unique_law_count": len(law_ids),
        "unique_law_ids": ";".join(law_ids),
        "unique_law_titles_preview": ";".join(law_titles[:LIST_PREVIEW_LIMIT]),
        "unique_article_count": len(article_ids),
        "selected_article_ids_preview": ";".join(article_ids[:LIST_PREVIEW_LIMIT]),
        "selected_article_nos_preview": ";".join(article_nos[:LIST_PREVIEW_LIMIT]),
        "has_legacy_or_unknown_law_id": has_legacy,
        "has_answer_maybe_truncated": has_truncated,
        "has_answer_insufficient_basis": has_insufficient,
        "answer_length_chars": len(answer),
        "answer_preview": _preview(answer, PREVIEW_LIMIT),
        "heuristic_category": heuristic_category,
        "heuristic_reason": heuristic_reason,
        "recommended_action": recommended_action,
    }


def classify_case(
    question: str,
    selected_count: int,
    unique_law_count: int,
    has_legacy_or_unknown_law_id: bool,
    has_answer_maybe_truncated: bool,
    has_answer_insufficient_basis: bool,
) -> tuple[str, str, str]:
    """Assign a diagnostic category using simple deterministic heuristics."""
    if has_answer_maybe_truncated:
        return (
            "answer_truncation_risk",
            "too_many_selected_articles overlaps answer_maybe_truncated",
            "reduce context budget pressure or selected article count before regeneration",
        )
    if has_answer_insufficient_basis:
        return (
            "insufficient_basis_risk",
            "answer reports insufficient basis despite many selected articles",
            "inspect whether selected articles are off-topic or missing canonical text",
        )
    if has_legacy_or_unknown_law_id:
        return (
            "legacy_or_version_noise",
            "selected articles contain legacy, unknown, or malformed law_id signals",
            "prioritize canonical law_id/version cleanup before selector changes",
        )
    if unique_law_count == 1 and selected_count >= 10:
        return (
            "same_law_many_articles",
            "many selected articles come from one law_id",
            "review selector article cap per law and keep only question-relevant articles",
        )
    if unique_law_count <= 2 and _has_multihop_signal(question):
        return (
            "likely_multihop_valid",
            "question has multi-hop/procedure signal and selected laws are concentrated",
            "keep as candidate valid multi-article case; manually sample quality",
        )
    if unique_law_count >= 4:
        return (
            "cross_law_possible_noise",
            "selected articles are spread across many law_ids",
            "inspect retrieval noise and future reranker/selector tightening",
        )
    if 2 <= unique_law_count <= 3 and selected_count >= 10:
        return (
            "selector_overinclusive",
            "selected_count is high with several law_ids and no answer risk flag",
            "tighten selector cap/diversity rules after manual review",
        )
    return (
        "unknown_needs_manual_review",
        "no strong deterministic heuristic matched",
        "manual sample review before changing retrieval or selector behavior",
    )


def build_law_distribution(report_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cases_by_law: dict[str, set[str]] = defaultdict(set)
    article_count_by_law: Counter[str] = Counter()
    titles_by_law: dict[str, str] = {}
    examples_by_law: dict[str, list[str]] = defaultdict(list)

    for row in report_rows:
        record_id = _safe_id(row.get("id"))
        law_ids = [law_id for law_id in _split_semicolon(row.get("unique_law_ids")) if law_id]
        law_titles = _split_semicolon(row.get("unique_law_titles_preview"))
        title_by_position = {law_id: law_titles[index] for index, law_id in enumerate(law_ids) if index < len(law_titles)}
        for law_id in law_ids:
            cases_by_law[law_id].add(record_id)
            article_count_by_law[law_id] += _count_articles_for_law(row, law_id)
            if law_id not in titles_by_law:
                titles_by_law[law_id] = title_by_position.get(law_id, "")
            if len(examples_by_law[law_id]) < 5:
                examples_by_law[law_id].append(record_id)

    rows = [
        {
            "law_id": law_id,
            "law_title": titles_by_law.get(law_id, ""),
            "case_count": len(case_ids),
            "article_count": article_count_by_law[law_id],
            "example_ids": ";".join(examples_by_law[law_id]),
        }
        for law_id, case_ids in cases_by_law.items()
    ]
    rows.sort(key=lambda row: (-int(row["case_count"]), -int(row["article_count"]), str(row["law_id"])))
    return rows


def build_selected_count_distribution(report_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    total = len(report_rows)
    counter = Counter(_safe_int(row.get("selected_count")) for row in report_rows)
    return [
        {
            "selected_count": selected_count,
            "case_count": case_count,
            "percentage": round((case_count / total * 100), 2) if total else 0.0,
        }
        for selected_count, case_count in sorted(counter.items())
    ]


def build_summary(
    report_rows: list[Mapping[str, Any]],
    law_distribution_rows: list[Mapping[str, Any]],
    count_distribution_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    category_counts = Counter(str(row.get("heuristic_category") or "") for row in report_rows)
    selected_count_distribution = {
        str(row["selected_count"]): row["case_count"] for row in count_distribution_rows
    }
    unique_law_count_distribution = Counter(_safe_int(row.get("unique_law_count")) for row in report_rows)
    top_noisy_law_ids = [
        {
            "law_id": row.get("law_id", ""),
            "law_title": row.get("law_title", ""),
            "case_count": row.get("case_count", 0),
            "article_count": row.get("article_count", 0),
            "example_ids": row.get("example_ids", ""),
        }
        for row in law_distribution_rows[:20]
    ]
    return {
        "total_too_many_selected_cases": len(report_rows),
        "category_counts": dict(category_counts),
        "selected_count_distribution": selected_count_distribution,
        "unique_law_count_distribution": {str(key): value for key, value in sorted(unique_law_count_distribution.items())},
        "overlap_with_legacy_or_unknown_law_id": sum(bool(row.get("has_legacy_or_unknown_law_id")) for row in report_rows),
        "overlap_with_answer_maybe_truncated": sum(bool(row.get("has_answer_maybe_truncated")) for row in report_rows),
        "overlap_with_answer_insufficient_basis": sum(bool(row.get("has_answer_insufficient_basis")) for row in report_rows),
        "top_noisy_law_ids": top_noisy_law_ids,
        "recommended_next_step": _recommended_next_step(category_counts),
    }


def write_samples_markdown(path: Path, report_rows: list[Mapping[str, Any]], summary: Mapping[str, Any]) -> None:
    rows_by_category: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in report_rows:
        rows_by_category[str(row.get("heuristic_category") or "unknown_needs_manual_review")].append(row)

    lines = [
        "# P6.R5 too_many_selected_articles samples",
        "",
        "## Summary",
        "",
        f"- Total cases: {summary.get('total_too_many_selected_cases', 0)}",
        f"- Category counts: {json.dumps(summary.get('category_counts', {}), ensure_ascii=False, sort_keys=True)}",
        "",
    ]
    for category in sorted(rows_by_category):
        lines.extend([f"## Category: {category}", ""])
        for row in rows_by_category[category][:5]:
            lines.extend(
                [
                    f"- id: {row.get('id', '')}",
                    f"  question: {_preview(str(row.get('question', '')), PREVIEW_LIMIT)}",
                    f"  selected_count: {row.get('selected_count', '')}",
                    f"  unique_law_ids: {row.get('unique_law_ids', '')}",
                    f"  selected_article_ids_preview: {row.get('selected_article_ids_preview', '')}",
                    f"  heuristic_reason: {row.get('heuristic_reason', '')}",
                    "",
                ]
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(path: Path, columns: list[str], rows: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def split_issue_categories(value: Any) -> set[str]:
    text = str(value or "")
    normalized = text.replace(";", ",").replace("|", ",")
    return {part.strip() for part in normalized.split(",") if part.strip()}


def _selected_articles(retrieval_record: Mapping[str, Any], answer_record: Mapping[str, Any]) -> list[Any]:
    retrieval_selected = _safe_list(retrieval_record.get("selected_articles"))
    if retrieval_selected:
        return retrieval_selected
    return _safe_list(answer_record.get("selected_articles"))


def _article_info(article: Any) -> dict[str, str]:
    if isinstance(article, Mapping):
        return {
            "article_id": _first_text(article.get("article_id"), article.get("legal_article_id")),
            "law_id": _safe_text(article.get("law_id")),
            "law_title": _safe_text(article.get("law_title")),
            "article_no": _first_text(article.get("article_no"), article.get("article_number")),
        }
    text = _safe_text(article)
    parts = [part.strip() for part in text.split("|")]
    if len(parts) >= 3:
        return {"article_id": text, "law_id": parts[0], "law_title": parts[1], "article_no": parts[2]}
    return {"article_id": text, "law_id": "", "law_title": "", "article_no": ""}


def _is_legacy_or_unknown_law_id(law_id: str) -> bool:
    normalized = _safe_text(law_id).casefold()
    if normalized in UNKNOWN_LAW_IDS:
        return True
    return any(year in normalized for year in ("1980", "1981", "1982", "1983", "1984", "1985", "1986", "1987", "1988", "1989"))


def _has_multihop_signal(question: str) -> bool:
    lowered = f" {_safe_text(question).casefold()} "
    return any(signal in lowered for signal in MULTIHOP_QUESTION_SIGNALS)


def _count_articles_for_law(row: Mapping[str, Any], law_id: str) -> int:
    law_ids = _split_semicolon(row.get("unique_law_ids"))
    if len(law_ids) == 1 and law_ids[0] == law_id:
        return _safe_int(row.get("unique_article_count"))
    return 1


def _recommended_next_step(category_counts: Counter[str]) -> str:
    if not category_counts:
        return "No too_many_selected_articles cases found."
    top_category, _ = category_counts.most_common(1)[0]
    if top_category == "legacy_or_version_noise":
        return "Prioritize canonical law_id/version cleanup before selector changes."
    if top_category in {"cross_law_possible_noise", "selector_overinclusive"}:
        return "Manually inspect samples, then consider Phase 7 reranker/selector tightening."
    if top_category == "answer_truncation_risk":
        return "Reduce prompt/context pressure for high selected_count cases before regeneration."
    return "Review category samples before changing retrieval or selector behavior."


def _split_semicolon(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def _dedupe_preserve_order(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _safe_id(value: Any) -> str:
    return _safe_text(value)


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
    return " ".join(str(value or "").split())[:limit]
