import csv
import json

from backend.evaluation.legacy_metadata_residual_analysis import (
    build_legacy_metadata_residual_analysis,
    build_summary,
    contains_khong_so,
    extract_selected_article_refs,
)


def test_parse_selected_articles_list_strings() -> None:
    row = {"selected_articles": ["12/2022/ND-CP|Nghi dinh 12|Dieu 1"]}

    refs = extract_selected_article_refs(row)

    assert len(refs) == 1
    assert refs[0].law_id == "12/2022/ND-CP"
    assert refs[0].law_title == "Nghi dinh 12"
    assert refs[0].article_no == "Dieu 1"


def test_parse_selected_articles_list_dicts() -> None:
    row = {"selected_articles": [{"article_id": "12/2022/ND-CP|Nghi dinh 12|Dieu 1"}]}

    refs = extract_selected_article_refs(row)

    assert len(refs) == 1
    assert refs[0].article_id == "12/2022/ND-CP|Nghi dinh 12|Dieu 1"


def test_detect_law_id_khong_so_from_selected(tmp_path) -> None:
    low, answers, retrieval = _write_inputs(
        tmp_path,
        low_rows=[_low_row("1", "legacy_or_unknown_law_id")],
        answers=[{"id": 1, "question": "Q1", "answer": "Answer"}],
        retrieval=[{"id": 1, "question": "Q1", "selected_articles": ["Khong so|Unknown title|Dieu 1"]}],
    )

    summary = build_legacy_metadata_residual_analysis(low, answers, retrieval, tmp_path / "out")
    rows = _read_csv(tmp_path / "out" / "legacy_metadata_residual_report.csv")

    assert summary["total_legacy_or_unknown_law_id"] == 1
    assert rows[0]["has_khong_so_in_selected"] == "True"
    assert "selected_contains_khong_so" in rows[0]["trigger_categories"]


def test_detect_empty_law_id(tmp_path) -> None:
    low, answers, retrieval = _write_inputs(
        tmp_path,
        low_rows=[_low_row("1", "legacy_or_unknown_law_id")],
        answers=[{"id": 1, "question": "Q1", "answer": "Answer"}],
        retrieval=[{"id": 1, "question": "Q1", "selected_articles": [{"law_id": "", "law_title": "Title", "article_no": "Dieu 1"}]}],
    )

    build_legacy_metadata_residual_analysis(low, answers, retrieval, tmp_path / "out")
    rows = _read_csv(tmp_path / "out" / "legacy_metadata_residual_report.csv")

    assert rows[0]["has_empty_law_id"] == "True"
    assert "selected_contains_empty_law_id" in rows[0]["trigger_categories"]


def test_detect_answer_mentions_khong_so() -> None:
    assert contains_khong_so("Can cu van ban Khong so ve ho so") is True


def test_detect_overlap_with_answer_insufficient_basis(tmp_path) -> None:
    low, answers, retrieval = _write_inputs(
        tmp_path,
        low_rows=[_low_row("1", "legacy_or_unknown_law_id;answer_insufficient_basis")],
        answers=[{"id": 1, "question": "Q1", "answer": "Answer"}],
        retrieval=[{"id": 1, "question": "Q1", "selected_articles": ["12/2022/ND-CP|Nghi dinh 12|Dieu 1"]}],
    )

    build_legacy_metadata_residual_analysis(low, answers, retrieval, tmp_path / "out")
    rows = _read_csv(tmp_path / "out" / "legacy_metadata_residual_report.csv")

    assert rows[0]["overlaps_answer_insufficient_basis"] == "True"


def test_summary_action_counts_are_computed() -> None:
    summary = build_summary(
        low_rows=[_low_row("1", "legacy_or_unknown_law_id"), _low_row("2", "legacy_or_unknown_law_id;answer_insufficient_basis")],
        report_rows=[
            {"id": "1", "recommended_action": "canonical_metadata_cleanup_needed", "trigger_categories": "needs_canonical_metadata_cleanup", "selected_law_ids": "Khong so"},
            {"id": "2", "recommended_action": "manual_review_needed", "trigger_categories": "heuristic_false_positive_candidate", "selected_law_ids": "12/2022/ND-CP"},
        ],
        low_confidence_path="low.csv",
        answers_path="answers.jsonl",
        retrieval_results_path="retrieval.jsonl",
    )

    assert summary["recommended_action_counts"]["canonical_metadata_cleanup_needed"] == 1
    assert summary["recommended_action_counts"]["manual_review_needed"] == 1
    assert summary["trigger_category_counts"]["needs_canonical_metadata_cleanup"] == 1


def test_report_rows_equal_filtered_legacy_cases(tmp_path) -> None:
    low, answers, retrieval = _write_inputs(
        tmp_path,
        low_rows=[
            _low_row("1", "legacy_or_unknown_law_id"),
            _low_row("2", "answer_insufficient_basis"),
            _low_row("3", "legacy_or_unknown_law_id;answer_insufficient_basis"),
        ],
        answers=[
            {"id": 1, "question": "Q1", "answer": "Answer 1"},
            {"id": 2, "question": "Q2", "answer": "Answer 2"},
            {"id": 3, "question": "Q3", "answer": "Answer 3"},
        ],
        retrieval=[
            {"id": 1, "question": "Q1", "selected_articles": ["12/2022/ND-CP|Nghi dinh 12|Dieu 1"]},
            {"id": 2, "question": "Q2", "selected_articles": ["12/2022/ND-CP|Nghi dinh 12|Dieu 2"]},
            {"id": 3, "question": "Q3", "selected_articles": ["Khong so|Title|Dieu 3"]},
        ],
    )

    summary = build_legacy_metadata_residual_analysis(low, answers, retrieval, tmp_path / "out")
    rows = _read_csv(tmp_path / "out" / "legacy_metadata_residual_report.csv")

    assert summary["total_low_confidence"] == 3
    assert summary["total_legacy_or_unknown_law_id"] == 2
    assert len(rows) == 2


def _low_row(row_id: str, issues: str) -> dict[str, str]:
    return {"id": row_id, "question": f"Q{row_id}", "issue_categories": issues}


def _write_inputs(tmp_path, low_rows, answers, retrieval):
    low = tmp_path / "low.csv"
    answers_path = tmp_path / "answers.jsonl"
    retrieval_path = tmp_path / "retrieval.jsonl"
    _write_csv(low, ["id", "question", "issue_categories"], low_rows)
    _write_jsonl(answers_path, answers)
    _write_jsonl(retrieval_path, retrieval)
    return low, answers_path, retrieval_path


def _write_csv(path, columns, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]
