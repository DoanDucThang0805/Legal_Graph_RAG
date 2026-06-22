"""Regenerate answers for rows changed by selector tightening experiments."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from backend.evaluation.generated_answer_merge import merge_generated_answer_subset
from backend.evaluation.subset_answer_regeneration import generate_answers_for_subset
from backend.qa.answer_generator import AnswerGenerator

CHANGED_IDS_FILENAME = "changed_selected_articles_ids.csv"
SUBSET_OUTPUT_FILENAME = "generated_answers_p6r6c_soft_10_7_subset.jsonl"
MERGED_OUTPUT_FILENAME = "generated_answers_p6r6c_soft_10_7_merged.jsonl"
REGENERATION_SUMMARY_FILENAME = "regeneration_summary.json"
MERGE_SUMMARY_FILENAME = "merge_summary.json"

CHANGED_COLUMNS = [
    "id",
    "question",
    "baseline_selected_count",
    "tightened_selected_count",
    "baseline_unique_law_count",
    "tightened_unique_law_count",
    "selected_count_delta",
    "unique_law_count_delta",
    "baseline_selected_articles_preview",
    "tightened_selected_articles_preview",
]


def find_changed_selected_article_ids(baseline_retrieval_path: str | Path, tightened_retrieval_path: str | Path) -> list[int]:
    rows = build_changed_selected_articles_rows(baseline_retrieval_path, tightened_retrieval_path)
    ids: list[int] = []
    for row in rows:
        try:
            ids.append(int(row["id"]))
        except (TypeError, ValueError):
            continue
    return ids


def build_changed_selected_articles_rows(
    baseline_retrieval_path: str | Path,
    tightened_retrieval_path: str | Path,
) -> list[dict[str, Any]]:
    baseline = read_jsonl_by_id(baseline_retrieval_path)
    tightened = read_jsonl_by_id(tightened_retrieval_path)
    rows: list[dict[str, Any]] = []
    for record_id, baseline_record in baseline.items():
        tightened_record = tightened.get(record_id)
        if not tightened_record:
            continue
        baseline_articles = extract_selected_article_ids(baseline_record)
        tightened_articles = extract_selected_article_ids(tightened_record)
        if baseline_articles == tightened_articles:
            continue
        baseline_laws = unique_law_ids(baseline_articles)
        tightened_laws = unique_law_ids(tightened_articles)
        rows.append(
            {
                "id": record_id,
                "question": _first_text(tightened_record.get("question"), baseline_record.get("question")),
                "baseline_selected_count": len(baseline_articles),
                "tightened_selected_count": len(tightened_articles),
                "baseline_unique_law_count": len(baseline_laws),
                "tightened_unique_law_count": len(tightened_laws),
                "selected_count_delta": len(baseline_articles) - len(tightened_articles),
                "unique_law_count_delta": len(baseline_laws) - len(tightened_laws),
                "baseline_selected_articles_preview": ";".join(baseline_articles[:8]),
                "tightened_selected_articles_preview": ";".join(tightened_articles[:8]),
            }
        )
    return rows


def write_changed_selected_articles_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CHANGED_COLUMNS)
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in CHANGED_COLUMNS} for row in rows)


def regenerate_tightened_selector_subset(
    baseline_retrieval_path: str | Path,
    tightened_retrieval_path: str | Path,
    output_dir: str | Path,
    legal_articles_path: str | Path,
    generator: AnswerGenerator,
    max_tokens: int = 256,
    max_article_chars: int = 1200,
    max_total_context_chars: int = 2600,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    changed_rows = build_changed_selected_articles_rows(baseline_retrieval_path, tightened_retrieval_path)
    changed_ids = [str(row["id"]) for row in changed_rows]
    changed_csv_path = output_path / CHANGED_IDS_FILENAME
    subset_output_path = output_path / SUBSET_OUTPUT_FILENAME
    write_changed_selected_articles_csv(changed_csv_path, changed_rows)

    if changed_ids:
        generation_summary = generate_answers_for_subset(
            retrieval_results_path=tightened_retrieval_path,
            output_path=subset_output_path,
            question_ids=changed_ids,
            legal_articles_path=legal_articles_path,
            generator=generator,
            max_tokens=max_tokens,
            max_article_chars=max_article_chars,
            max_total_context_chars=max_total_context_chars,
        )
    else:
        subset_output_path.write_text("", encoding="utf-8")
        generation_summary = {"requested": 0, "processed": 0, "missing": 0, "missing_ids": [], "output_path": str(subset_output_path)}

    summary = {
        "changed_count": len(changed_rows),
        "changed_ids_csv_path": str(changed_csv_path),
        "subset_output_path": str(subset_output_path),
        "baseline_retrieval_path": str(baseline_retrieval_path),
        "tightened_retrieval_path": str(tightened_retrieval_path),
        "generation_summary": generation_summary,
        "expected_changed_count_hint": 284,
        "changed_count_matches_expected_hint": len(changed_rows) == 284,
    }
    write_json(output_path / REGENERATION_SUMMARY_FILENAME, summary)
    return summary


def merge_tightened_selector_subset(base_path: str | Path, subset_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    summary = merge_generated_answer_subset(base_path, subset_path, output_path)
    summary_path = Path(output_path).parent / MERGE_SUMMARY_FILENAME
    write_json(summary_path, summary)
    summary["merge_summary_path"] = str(summary_path)
    return summary


def read_jsonl_by_id(path: str | Path) -> dict[str, dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"JSONL input does not exist: {source}")
    records: dict[str, dict[str, Any]] = {}
    with source.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            loaded = json.loads(line)
            if not isinstance(loaded, dict):
                raise ValueError(f"JSONL line {line_number} must be an object")
            record_id = _safe_text(loaded.get("id"))
            if record_id:
                records[record_id] = loaded
    return records


def extract_selected_article_ids(record: dict[str, Any]) -> list[str]:
    selected = record.get("selected_articles")
    if not isinstance(selected, list):
        return []
    result: list[str] = []
    for item in selected:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict) and item.get("article_id"):
            result.append(str(item["article_id"]).strip())
    return result


def unique_law_ids(article_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for article_id in article_ids:
        law_id = str(article_id or "").split("|", 1)[0].strip() or "__UNKNOWN__"
        if law_id in seen:
            continue
        seen.add(law_id)
        result.append(law_id)
    return result


def write_json(path: str | Path, value: Any) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return ""


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
