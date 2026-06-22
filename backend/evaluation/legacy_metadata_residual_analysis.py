"""Analyze residual legacy/unknown law metadata issues after answer fixes."""

from __future__ import annotations

import csv
import json
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.evaluation.selector_tightening_experiment import ArticleRef, parse_article_id
from backend.evaluation.unsupported_citations import build_supported_citation_keys, extract_answer_citations

logger = logging.getLogger(__name__)

REPORT_FILENAME = "legacy_metadata_residual_report.csv"
SUMMARY_FILENAME = "legacy_metadata_residual_summary.json"
SAMPLES_FILENAME = "legacy_metadata_residual_samples.md"
RECOMMENDATIONS_FILENAME = "candidate_fix_recommendations.md"

LEGACY_ISSUE = "legacy_or_unknown_law_id"
INSUFFICIENT_BASIS_ISSUE = "answer_insufficient_basis"
UNSUPPORTED_CITATION_ISSUE = "unsupported_citation_in_answer"
TOO_MANY_ISSUE = "too_many_selected_articles"
TRUNCATED_ISSUE = "answer_maybe_truncated"

UNKNOWN_LAW_TOKENS = {"", "unknown", "none", "null", "__unknown__", "khong so", "khong ro"}
OLD_YEAR_PATTERN = re.compile(r"\b(19\d{2}|200[0-9]|201[0-7])\b")
LAW_ID_PATTERN = re.compile(
    r"\b\d{1,4}/\d{4}/(?:QH\d*|NĐ-CP|ND-CP|TT-[A-ZĐ0-9-]+|QD-[A-ZĐ0-9-]+|QĐ-[A-ZĐ0-9-]+)\b",
    flags=re.IGNORECASE,
)

REPORT_COLUMNS = [
    "id",
    "question",
    "issue_categories",
    "answer_preview",
    "selected_count",
    "selected_article_ids_preview",
    "selected_law_ids",
    "answer_mentioned_law_ids",
    "legacy_triggers",
    "trigger_categories",
    "has_khong_so_in_answer",
    "has_khong_so_in_selected",
    "has_empty_law_id",
    "has_unknown_law_id",
    "has_legacy_version_signal",
    "has_title_mismatch_signal",
    "has_outdated_document_signal",
    "answer_citation_allows_selected",
    "overlaps_answer_insufficient_basis",
    "recommended_action",
]


@dataclass(frozen=True)
class LegacyAnalysisInputs:
    low_confidence_path: str | Path
    answers_path: str | Path
    retrieval_results_path: str | Path
    output_dir: str | Path
    canonical_articles_path: str | Path | None = None


def build_legacy_metadata_residual_analysis(
    low_confidence_path: str | Path,
    answers_path: str | Path,
    retrieval_results_path: str | Path,
    output_dir: str | Path,
    canonical_articles_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build residual legacy metadata reports without changing retrieval or answers."""
    low_rows = read_csv_rows(low_confidence_path)
    answer_rows = read_jsonl_by_id(answers_path)
    retrieval_rows = read_jsonl_by_id(retrieval_results_path)

    legacy_rows = [row for row in low_rows if LEGACY_ISSUE in split_issue_categories(row.get("issue_categories"))]
    report_rows = [
        build_report_row(row, answer_rows.get(_safe_text(row.get("id")), {}), retrieval_rows.get(_safe_text(row.get("id")), {}))
        for row in legacy_rows
    ]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / REPORT_FILENAME
    summary_path = output_path / SUMMARY_FILENAME
    samples_path = output_path / SAMPLES_FILENAME
    recommendations_path = output_path / RECOMMENDATIONS_FILENAME

    write_csv(report_path, REPORT_COLUMNS, report_rows)
    summary = build_summary(
        low_rows=low_rows,
        report_rows=report_rows,
        low_confidence_path=low_confidence_path,
        answers_path=answers_path,
        retrieval_results_path=retrieval_results_path,
        canonical_articles_path=canonical_articles_path,
    )
    write_json(summary_path, summary)
    write_samples_markdown(samples_path, report_rows)
    write_recommendations_markdown(recommendations_path, summary)

    return {
        **summary,
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "samples_path": str(samples_path),
        "recommendations_path": str(recommendations_path),
    }


def build_report_row(
    low_confidence_row: Mapping[str, Any],
    answer_row: Mapping[str, Any],
    retrieval_row: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify one low-confidence legacy metadata row."""
    record_id = _safe_text(low_confidence_row.get("id"))
    issue_categories = split_issue_categories(low_confidence_row.get("issue_categories"))
    answer = _first_text(answer_row.get("answer"), low_confidence_row.get("answer"))
    selected_refs = extract_selected_article_refs(retrieval_row)
    selected_law_ids = _dedup_texts(ref.law_id for ref in selected_refs if ref.law_id)
    answer_law_ids = extract_answer_law_ids(answer)

    flags = {
        "has_khong_so_in_answer": contains_khong_so(answer),
        "has_khong_so_in_selected": any(is_unknown_law_id(ref.law_id) for ref in selected_refs),
        "has_empty_law_id": any(not _safe_text(ref.law_id) for ref in selected_refs),
        "has_unknown_law_id": any(is_unknown_law_id(ref.law_id) for ref in selected_refs) or contains_unknown_law_id_text(answer),
        "has_legacy_version_signal": any(has_legacy_version_signal(ref) for ref in selected_refs),
        "has_title_mismatch_signal": any(has_title_mismatch_signal(ref) for ref in selected_refs),
        "has_outdated_document_signal": any(has_outdated_document_signal(ref) for ref in selected_refs),
        "overlaps_answer_insufficient_basis": INSUFFICIENT_BASIS_ISSUE in issue_categories,
    }
    flags["answer_citation_allows_selected"] = answer_citation_allows_selected(answer, selected_refs)

    trigger_categories = classify_trigger_categories(flags)
    recommended_action = recommend_action(flags, trigger_categories)
    legacy_triggers = build_legacy_triggers(selected_refs, answer, flags)

    return {
        "id": record_id,
        "question": _first_text(low_confidence_row.get("question"), answer_row.get("question"), retrieval_row.get("question")),
        "issue_categories": ";".join(issue_categories),
        "answer_preview": _preview(answer, 320),
        "selected_count": len(selected_refs),
        "selected_article_ids_preview": ";".join(ref.article_id for ref in selected_refs[:8]),
        "selected_law_ids": ";".join(selected_law_ids),
        "answer_mentioned_law_ids": ";".join(answer_law_ids),
        "legacy_triggers": ";".join(legacy_triggers),
        "trigger_categories": ";".join(trigger_categories),
        "has_khong_so_in_answer": flags["has_khong_so_in_answer"],
        "has_khong_so_in_selected": flags["has_khong_so_in_selected"],
        "has_empty_law_id": flags["has_empty_law_id"],
        "has_unknown_law_id": flags["has_unknown_law_id"],
        "has_legacy_version_signal": flags["has_legacy_version_signal"],
        "has_title_mismatch_signal": flags["has_title_mismatch_signal"],
        "has_outdated_document_signal": flags["has_outdated_document_signal"],
        "answer_citation_allows_selected": flags["answer_citation_allows_selected"],
        "overlaps_answer_insufficient_basis": flags["overlaps_answer_insufficient_basis"],
        "recommended_action": recommended_action,
    }


def extract_selected_article_refs(record: Mapping[str, Any]) -> list[ArticleRef]:
    """Parse selected_articles from both list[str] and list[dict] schemas."""
    selected = record.get("selected_articles")
    if not isinstance(selected, list):
        return []

    refs: list[ArticleRef] = []
    for item in selected:
        if isinstance(item, str):
            refs.append(parse_article_id(item))
            continue
        if isinstance(item, Mapping):
            article_id = _first_text(item.get("article_id"), item.get("legal_article_id"))
            if article_id:
                parsed = parse_article_id(article_id)
                refs.append(
                    ArticleRef(
                        article_id=parsed.article_id,
                        law_id=_first_text(item.get("law_id"), parsed.law_id),
                        law_title=_first_text(item.get("law_title"), parsed.law_title),
                        article_no=_first_text(item.get("article_no"), parsed.article_no),
                    )
                )
                continue
            refs.append(
                ArticleRef(
                    article_id="",
                    law_id=_safe_text(item.get("law_id")),
                    law_title=_safe_text(item.get("law_title")),
                    article_no=_safe_text(item.get("article_no")),
                )
            )
    return refs


def extract_answer_law_ids(answer: str) -> list[str]:
    """Extract law IDs mentioned anywhere in an answer."""
    ids: list[str] = []
    seen: set[str] = set()
    for match in LAW_ID_PATTERN.finditer(str(answer or "")):
        law_id = match.group(0).upper().replace("ND-CP", "NĐ-CP").replace("QD-", "QĐ-")
        if law_id not in seen:
            seen.add(law_id)
            ids.append(law_id)
    return ids


def contains_khong_so(value: Any) -> bool:
    return "khong so" in _ascii_fold(value)


def contains_unknown_law_id_text(value: Any) -> bool:
    folded = _ascii_fold(value)
    return any(token and token in folded for token in UNKNOWN_LAW_TOKENS if token)


def is_unknown_law_id(value: Any) -> bool:
    return _ascii_fold(value) in UNKNOWN_LAW_TOKENS


def has_legacy_version_signal(ref: ArticleRef) -> bool:
    text = f"{ref.law_id} {ref.law_title} {ref.article_id}"
    return bool(OLD_YEAR_PATTERN.search(text))


def has_outdated_document_signal(ref: ArticleRef) -> bool:
    folded = _ascii_fold(f"{ref.law_title} {ref.article_id}")
    legacy_keywords = ("het hieu luc", "bi thay the", "sua doi bo sung", "bo luat dan su 2005", "luat doanh nghiep 2014")
    return has_legacy_version_signal(ref) or any(keyword in folded for keyword in legacy_keywords)


def has_title_mismatch_signal(ref: ArticleRef) -> bool:
    if not ref.law_id or not ref.law_title:
        return False
    title_ids = {law_id.upper().replace("ND-CP", "NĐ-CP").replace("QD-", "QĐ-") for law_id in LAW_ID_PATTERN.findall(ref.law_title)}
    return bool(title_ids and ref.law_id.upper() not in title_ids)


def answer_citation_allows_selected(answer: str, selected_refs: Sequence[ArticleRef]) -> bool:
    citations = extract_answer_citations(answer)
    if not citations:
        return True
    selected_articles = [
        {"law_id": ref.law_id, "article_no": ref.article_no, "article_id": ref.article_id}
        for ref in selected_refs
    ]
    supported = build_supported_citation_keys(selected_articles)
    return all((citation.article_no.casefold(), (citation.law_id or "").casefold()) in supported for citation in citations)


def classify_trigger_categories(flags: Mapping[str, bool]) -> list[str]:
    categories: list[str] = []
    if flags.get("has_khong_so_in_answer"):
        categories.append("answer_mentions_khong_so")
    if flags.get("has_khong_so_in_selected"):
        categories.append("selected_contains_khong_so")
    if flags.get("has_empty_law_id"):
        categories.append("selected_contains_empty_law_id")
    if flags.get("has_unknown_law_id") and not flags.get("has_khong_so_in_selected"):
        categories.append("answer_mentions_unknown_law_id")
    if flags.get("has_outdated_document_signal"):
        categories.append("selected_contains_old_code_or_legacy_doc")
    if flags.get("has_title_mismatch_signal"):
        categories.append("title_mismatch_suspected")
    if flags.get("has_legacy_version_signal"):
        categories.append("version_overlap_suspected")

    # Phan tach false positive: citation van nam trong selected va khong co dau hieu unknown ro rang.
    if flags.get("answer_citation_allows_selected") and not any(
        flags.get(key)
        for key in ("has_khong_so_in_answer", "has_khong_so_in_selected", "has_empty_law_id", "has_unknown_law_id", "has_title_mismatch_signal")
    ):
        categories.append("heuristic_false_positive_candidate")

    if flags.get("has_khong_so_in_selected") or flags.get("has_empty_law_id") or flags.get("has_title_mismatch_signal"):
        categories.append("needs_canonical_metadata_cleanup")
    if flags.get("has_khong_so_in_answer"):
        categories.append("needs_answer_patch")
    if flags.get("has_outdated_document_signal"):
        categories.append("needs_retrieval_filtering")
    if not flags.get("answer_citation_allows_selected"):
        categories.append("needs_phase7_verifier")
    return _dedup_texts(categories)


def recommend_action(flags: Mapping[str, bool], trigger_categories: Sequence[str]) -> str:
    categories = set(trigger_categories)
    if "heuristic_false_positive_candidate" in categories:
        return "no_action_false_positive"
    if flags.get("has_khong_so_in_answer") and flags.get("answer_citation_allows_selected"):
        return "answer_patch_possible"
    if "needs_canonical_metadata_cleanup" in categories:
        return "canonical_metadata_cleanup_needed"
    if "needs_retrieval_filtering" in categories:
        return "retrieval_filtering_needed"
    if "needs_phase7_verifier" in categories:
        return "phase7_verifier_needed"
    return "manual_review_needed"


def build_legacy_triggers(selected_refs: Sequence[ArticleRef], answer: str, flags: Mapping[str, bool]) -> list[str]:
    triggers: list[str] = []
    if flags.get("has_khong_so_in_answer"):
        triggers.append("answer contains Khong so")
    for ref in selected_refs:
        if is_unknown_law_id(ref.law_id):
            triggers.append(f"unknown law_id: {ref.article_id or ref.law_title}")
        if not ref.law_id:
            triggers.append(f"empty law_id: {ref.article_id or ref.law_title}")
        if has_title_mismatch_signal(ref):
            triggers.append(f"title mismatch: {ref.law_id}|{ref.law_title}")
        if has_outdated_document_signal(ref):
            triggers.append(f"legacy/outdated signal: {ref.law_id}|{ref.law_title}")
    if not triggers and answer:
        triggers.append("legacy heuristic from low_confidence report")
    return _dedup_texts(triggers)[:12]


def build_summary(
    low_rows: Sequence[Mapping[str, Any]],
    report_rows: Sequence[Mapping[str, Any]],
    low_confidence_path: str | Path,
    answers_path: str | Path,
    retrieval_results_path: str | Path,
    canonical_articles_path: str | Path | None = None,
) -> dict[str, Any]:
    all_issue_counts = Counter(issue for row in low_rows for issue in split_issue_categories(row.get("issue_categories")))
    trigger_counts = Counter(
        category
        for row in report_rows
        for category in split_semicolon_text(row.get("trigger_categories"))
    )
    action_counts = Counter(_safe_text(row.get("recommended_action")) for row in report_rows if _safe_text(row.get("recommended_action")))
    top_law_ids = Counter(
        law_id
        for row in report_rows
        for law_id in split_semicolon_text(row.get("selected_law_ids"))
        if law_id
    ).most_common(20)
    top_law_titles = Counter(_extract_title_from_article_id(article_id) for row in report_rows for article_id in split_semicolon_text(row.get("selected_article_ids_preview")) if article_id).most_common(20)

    sample_ids_by_category: dict[str, list[str]] = defaultdict(list)
    for row in report_rows:
        row_id = _safe_text(row.get("id"))
        for category in split_semicolon_text(row.get("trigger_categories")):
            if row_id and len(sample_ids_by_category[category]) < 10:
                sample_ids_by_category[category].append(row_id)

    return {
        "total_low_confidence": len(low_rows),
        "total_legacy_or_unknown_law_id": len(report_rows),
        "unsupported_citation_count_current": all_issue_counts.get(UNSUPPORTED_CITATION_ISSUE, 0),
        "too_many_selected_articles_current": all_issue_counts.get(TOO_MANY_ISSUE, 0),
        "answer_maybe_truncated_current": all_issue_counts.get(TRUNCATED_ISSUE, 0),
        "answer_insufficient_basis_current": all_issue_counts.get(INSUFFICIENT_BASIS_ISSUE, 0),
        "trigger_category_counts": dict(sorted(trigger_counts.items())),
        "recommended_action_counts": dict(sorted(action_counts.items())),
        "overlap_with_answer_insufficient_basis": sum(_as_bool(row.get("overlaps_answer_insufficient_basis")) for row in report_rows),
        "top_legacy_law_ids": [{"law_id": key, "count": count} for key, count in top_law_ids],
        "top_legacy_law_titles": [{"law_title": key, "count": count} for key, count in top_law_titles if key],
        "sample_ids_by_category": dict(sample_ids_by_category),
        "final_recommendation": final_recommendation(trigger_counts, action_counts),
        "input_paths": {
            "low_confidence": str(low_confidence_path),
            "answers": str(answers_path),
            "retrieval_results": str(retrieval_results_path),
            "canonical_articles": str(canonical_articles_path) if canonical_articles_path else "",
        },
    }


def final_recommendation(trigger_counts: Counter[str], action_counts: Counter[str]) -> str:
    if not action_counts:
        return "manual_review_needed"
    dominant_action, dominant_count = action_counts.most_common(1)[0]
    total = sum(action_counts.values()) or 1
    if dominant_action == "canonical_metadata_cleanup_needed" and dominant_count / total >= 0.4:
        return "Prioritize canonical metadata cleanup for Khong so, empty law_id, and title mismatch cases before Phase 7."
    if dominant_action == "answer_patch_possible" and dominant_count / total >= 0.4:
        return "Prioritize targeted answer patching for answers that mention Khong so while selected citations remain supported."
    if dominant_action == "retrieval_filtering_needed" and dominant_count / total >= 0.4:
        return "Prioritize retrieval filtering or metadata quarantine for legacy/outdated documents."
    if trigger_counts.get("heuristic_false_positive_candidate", 0) / total >= 0.4:
        return "Many cases look like heuristic false positives; inspect samples before changing retrieval."
    return "Mixed residual legacy metadata cases; inspect category samples and choose cleanup versus retrieval filtering per group."


def write_samples_markdown(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        action = _safe_text(row.get("recommended_action")) or "manual_review_needed"
        if len(grouped[action]) < 8:
            grouped[action].append(row)

    lines = ["# P6.R7 Legacy Metadata Residual Samples", "", f"- Rows: {len(rows)}", ""]
    for action, samples in sorted(grouped.items()):
        lines.extend([f"## {action}", ""])
        for row in samples:
            lines.extend(
                [
                    f"- id: {row.get('id')}",
                    f"  question: {_preview(row.get('question'), 220)}",
                    f"  triggers: {row.get('trigger_categories')}",
                    f"  selected_law_ids: {row.get('selected_law_ids')}",
                    "",
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_recommendations_markdown(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# P6.R7 Candidate Fix Recommendations",
        "",
        f"- Total legacy_or_unknown_law_id: {summary.get('total_legacy_or_unknown_law_id')}",
        f"- Final recommendation: {summary.get('final_recommendation')}",
        "",
        "## Recommended Action Counts",
        "",
    ]
    for action, count in dict(summary.get("recommended_action_counts", {})).items():
        lines.append(f"- {action}: {count}")
    lines.extend(["", "## Trigger Category Counts", ""])
    for category, count in dict(summary.get("trigger_category_counts", {})).items():
        lines.append(f"- {category}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"CSV input does not exist: {source}")
    with source.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def read_jsonl_by_id(path: str | Path) -> dict[str, dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"JSONL input does not exist: {source}")
    records: dict[str, dict[str, Any]] = {}
    with source.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            loaded = json.loads(line)
            if not isinstance(loaded, dict):
                raise ValueError(f"JSONL line {line_number} must be an object")
            record_id = _safe_text(loaded.get("id"))
            if record_id:
                records[record_id] = loaded
    return records


def write_csv(path: Path, columns: list[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def split_issue_categories(value: Any) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    return _dedup_texts(part.strip() for part in re.split(r"[;,|]", text) if part.strip())


def split_semicolon_text(value: Any) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _dedup_texts(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe_text(value)
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _ascii_fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _safe_text(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.casefold().split())


def _extract_title_from_article_id(article_id: str) -> str:
    parts = [part.strip() for part in _safe_text(article_id).split("|")]
    return parts[1] if len(parts) >= 2 else ""


def _preview(value: Any, limit: int) -> str:
    text = " ".join(_safe_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return ""


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _safe_text(value).casefold() in {"true", "1", "yes"}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
