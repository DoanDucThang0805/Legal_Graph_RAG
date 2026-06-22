import csv
import json

from backend.evaluation.too_many_selected_analysis import (
    build_summary,
    build_too_many_selected_analysis,
    build_question_report_row,
    filter_too_many_selected_rows,
)


def test_filter_too_many_selected_rows_matches_issue_category() -> None:
    rows = [
        {"id": "1", "issue_categories": "too_many_selected_articles;answer_maybe_truncated"},
        {"id": "2", "issue_categories": "answer_maybe_truncated"},
        {"id": "3", "issue_categories": "legacy_or_unknown_law_id|too_many_selected_articles"},
    ]

    filtered = filter_too_many_selected_rows(rows)

    assert [row["id"] for row in filtered] == ["1", "3"]


def test_build_question_report_row_joins_retrieval_and_answer_fields() -> None:
    low_row = {
        "id": "42",
        "question": "Fallback question",
        "issue_categories": "too_many_selected_articles;answer_maybe_truncated;legacy_or_unknown_law_id",
        "selected_count": "10",
    }
    retrieval = {
        "id": "42",
        "question": "Question from retrieval",
        "selected_articles": [
            {"article_id": "old|Law A|Article 1", "law_id": "unknown", "law_title": "Law A", "article_no": "Article 1"},
            {"article_id": "36/2005/QH11|Law B|Article 2", "law_id": "36/2005/QH11", "law_title": "Law B", "article_no": "Article 2"},
            {"article_id": "36/2005/QH11|Law B|Article 3", "law_id": "36/2005/QH11", "law_title": "Law B", "article_no": "Article 3"},
        ],
    }
    answer = {"id": "42", "answer": "Answer text"}

    row = build_question_report_row(low_row, retrieval, answer)

    assert row["question"] == "Question from retrieval"
    assert row["selected_count"] == 10
    assert row["unique_law_count"] == 2
    assert row["unique_law_ids"] == "unknown;36/2005/QH11"
    assert row["unique_article_count"] == 3
    assert row["has_legacy_or_unknown_law_id"] is True
    assert row["has_answer_maybe_truncated"] is True
    assert row["has_answer_insufficient_basis"] is False
    assert row["answer_length_chars"] == len("Answer text")
    assert row["heuristic_category"] == "answer_truncation_risk"


def test_category_fallback_does_not_crash_when_fields_are_missing() -> None:
    low_row = {"id": "99", "issue_categories": "too_many_selected_articles"}

    row = build_question_report_row(low_row, {}, {})

    assert row["id"] == "99"
    assert row["selected_count"] == 0
    assert row["unique_law_count"] == 0
    assert row["heuristic_category"] == "unknown_needs_manual_review"


def test_build_summary_category_counts_sum_to_total() -> None:
    report_rows = [
        {"heuristic_category": "same_law_many_articles", "selected_count": 10, "unique_law_count": 1},
        {"heuristic_category": "same_law_many_articles", "selected_count": 10, "unique_law_count": 1},
        {"heuristic_category": "cross_law_possible_noise", "selected_count": 12, "unique_law_count": 4},
    ]

    summary = build_summary(report_rows, [], [{"selected_count": 10, "case_count": 2}, {"selected_count": 12, "case_count": 1}])

    assert summary["total_too_many_selected_cases"] == 3
    assert sum(summary["category_counts"].values()) == 3
    assert summary["category_counts"] == {"same_law_many_articles": 2, "cross_law_possible_noise": 1}


def test_runtime_analysis_writes_reports_and_does_not_overwrite_inputs(tmp_path) -> None:
    low_path = tmp_path / "low_confidence_questions.csv"
    retrieval_path = tmp_path / "retrieval_results.jsonl"
    answers_path = tmp_path / "answers.jsonl"
    output_dir = tmp_path / "reports"

    _write_csv(
        low_path,
        ["id", "question", "issue_categories", "selected_count"],
        [
            {"id": "1", "question": "Q1", "issue_categories": "too_many_selected_articles", "selected_count": "10"},
            {"id": "2", "question": "Q2", "issue_categories": "answer_maybe_truncated", "selected_count": "3"},
        ],
    )
    original_low_content = low_path.read_text(encoding="utf-8")
    _write_jsonl(
        retrieval_path,
        [
            {
                "id": 1,
                "question": "Q1 retrieval",
                "selected_articles": [
                    {"article_id": "36/2005/QH11|Law B|Article 1", "law_id": "36/2005/QH11", "law_title": "Law B", "article_no": "Article 1"}
                    for _ in range(10)
                ],
            }
        ],
    )
    _write_jsonl(answers_path, [{"id": 1, "answer": "A1"}])

    summary = build_too_many_selected_analysis(low_path, retrieval_path, output_dir, answers_path)

    assert summary["total_too_many_selected_cases"] == 1
    assert (output_dir / "too_many_selected_articles_report.csv").exists()
    assert (output_dir / "too_many_selected_articles_summary.json").exists()
    assert (output_dir / "too_many_selected_articles_law_distribution.csv").exists()
    assert (output_dir / "too_many_selected_articles_count_distribution.csv").exists()
    assert (output_dir / "too_many_selected_articles_samples.md").exists()
    assert low_path.read_text(encoding="utf-8") == original_low_content


def _write_csv(path, columns, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
