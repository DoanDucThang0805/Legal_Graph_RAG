from __future__ import annotations

import csv
import json
from pathlib import Path

import polars as pl

from backend.evaluation.canonical_legacy_cleanup_analysis import (
    build_candidate_metadata_cleanup_rules,
    build_canonical_legacy_cleanup_plan,
    detect_family,
    parse_selected_articles,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_parse_selected_articles_string_list() -> None:
    rows = parse_selected_articles([
        "Không số|Bộ luật Lao động số Không số|Điều 1",
        "45/2019/QH14|Bộ luật Lao động 2019|Điều 1",
    ])
    assert rows[0]["law_id"] == "Không số"
    assert rows[0]["article_no"] == "Điều 1"
    assert rows[1]["rank"] == 2


def test_parse_selected_articles_dict_list() -> None:
    rows = parse_selected_articles([
        {"article_id": "45/2019/QH14|Bộ luật Lao động 2019|Điều 2", "score": 1.0},
        {"law_id": "33/2005/QH11", "law_title": "Bộ luật Dân sự 2005", "article_no": "Điều 1"},
    ])
    assert rows[0]["law_id"] == "45/2019/QH14"
    assert rows[1]["article_id"] == "33/2005/QH11|Bộ luật Dân sự 2005|Điều 1"


def test_detect_family_labor_code() -> None:
    assert detect_family("45/2019/QH14", "Bộ luật Lao động 2019") == "Bộ luật Lao động"


def test_metadata_cleanup_rules_are_disabled_display_only() -> None:
    rules = build_candidate_metadata_cleanup_rules()
    assert rules["enabled_by_default"] is False
    assert rules["display_only"] is True
    assert all(rule["enabled"] is False for rule in rules["rules"])


def test_build_canonical_legacy_cleanup_plan_outputs_reports(tmp_path: Path) -> None:
    canonical_path = tmp_path / "legal_articles.parquet"
    residual_path = tmp_path / "residual.csv"
    low_path = tmp_path / "low.csv"
    retrieval_path = tmp_path / "retrieval.jsonl"
    answers_path = tmp_path / "answers.jsonl"
    output_dir = tmp_path / "out"

    old_article = "Không số|Bộ luật Lao động số Không số|Điều 1"
    modern_article = "45/2019/QH14|Bộ luật Lao động 2019|Điều 1"
    civil_article = "33/2005/QH11|Bộ luật Dân sự 2005|Điều 1"
    missing_article = "MISSING|Văn bản thiếu|Điều 9"

    pl.DataFrame(
        [
            {
                "article_id": old_article,
                "law_id": "Không số",
                "law_title": "Bộ luật Lao động số Không số",
                "article_no": "Điều 1",
                "source_url": "https://example.test/old",
                "domain": "labor",
                "status": "unknown",
            },
            {
                "article_id": modern_article,
                "law_id": "45/2019/QH14",
                "law_title": "Bộ luật Lao động 2019",
                "article_no": "Điều 1",
                "source_url": "https://example.test/new",
                "domain": "labor",
                "status": "active",
            },
            {
                "article_id": civil_article,
                "law_id": "33/2005/QH11",
                "law_title": "Bộ luật Dân sự 2005",
                "article_no": "Điều 1",
                "source_url": "https://example.test/civil",
                "domain": "civil",
                "status": "expired",
            },
        ]
    ).write_parquet(canonical_path)

    _write_csv(
        residual_path,
        [
            {
                "question_id": "1",
                "question": "Câu hỏi lao động",
                "selected_contains_khong_so": "true",
                "selected_contains_old_code_or_legacy_doc": "false",
                "version_overlap_suspected": "true",
                "needs_canonical_metadata_cleanup": "true",
                "needs_retrieval_filtering": "true",
            },
            {
                "question_id": "2",
                "question": "Câu hỏi dân sự cũ",
                "selected_contains_khong_so": "false",
                "selected_contains_old_code_or_legacy_doc": "true",
                "version_overlap_suspected": "false",
                "needs_canonical_metadata_cleanup": "false",
                "needs_retrieval_filtering": "false",
            },
        ],
    )
    _write_csv(low_path, [{"question_id": "1", "question": "Câu hỏi lao động"}, {"question_id": "2", "question": "Câu hỏi dân sự cũ"}])
    _write_jsonl(
        retrieval_path,
        [
            {"id": 1, "question": "Câu hỏi lao động", "selected_articles": [old_article, modern_article, missing_article]},
            {"id": 2, "question": "Câu hỏi dân sự cũ", "selected_articles": [{"article_id": civil_article}]},
        ],
    )
    _write_jsonl(answers_path, [{"id": 1, "answer": "Theo Điều 1 Bộ luật Lao động."}, {"id": 2, "answer": "Theo Điều 1."}])

    summary = build_canonical_legacy_cleanup_plan(
        residual_report_path=residual_path,
        low_confidence_path=low_path,
        retrieval_results_path=retrieval_path,
        answers_path=answers_path,
        canonical_articles_path=canonical_path,
        output_dir=output_dir,
    )

    assert summary["total_residual_rows"] == 2
    assert summary["total_selected_article_refs_scanned"] == 4
    assert summary["khong_so_article_count"] == 1
    assert summary["canonical_join_missing_count"] == 1
    assert summary["anomaly_category_counts"]["law_id_khong_so"] == 1
    assert summary["anomaly_category_counts"]["selected_article_not_found_in_canonical"] == 1
    assert (output_dir / "canonical_legacy_metadata_report.csv").exists()
    assert (output_dir / "canonical_legacy_grouped_by_article.csv").exists()
    assert (output_dir / "canonical_legacy_grouped_by_law.csv").exists()
    assert (output_dir / "canonical_legacy_cleanup_summary.json").exists()
    assert (output_dir / "canonical_legacy_cleanup_plan.md").exists()
    assert (output_dir / "candidate_retrieval_filter_rules.json").exists()
    assert (output_dir / "candidate_metadata_cleanup_rules.json").exists()

    report = list(csv.DictReader((output_dir / "canonical_legacy_metadata_report.csv").open("r", encoding="utf-8")))
    old_row = next(row for row in report if row["article_id"] == old_article)
    civil_row = next(row for row in report if row["article_id"] == civil_article)
    missing_row = next(row for row in report if row["article_id"] == missing_article)
    assert "law_title_contains_khong_so" in old_row["anomaly_categories"]
    assert old_row["recommended_action"] == "exact_alias_mapping_candidate"
    assert civil_row["recommended_action"] == "keep_no_action"
    assert missing_row["recommended_action"] == "manual_review_required"
