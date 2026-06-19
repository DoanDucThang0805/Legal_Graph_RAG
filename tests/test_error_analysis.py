import csv
import json
from pathlib import Path

from backend.evaluation.error_analysis import build_error_analysis_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_build_error_analysis_report_creates_csv_outputs(tmp_path: Path) -> None:
    retrieval_path = tmp_path / "retrieval_results.jsonl"
    answers_path = tmp_path / "generated_answers.jsonl"
    output_dir = tmp_path / "error_analysis"

    _write_jsonl(
        retrieval_path,
        [
            {
                "id": 1,
                "question": "Theo Điều 4 Luật hỗ trợ DNNVV thì sao?",
                "selected_articles": ["article-1"],
                "candidate_count": 3,
                "debug": {
                    "stage_counts": {
                        "bm25_legal": 2,
                        "dense_legal": 1,
                        "exact": 0,
                        "phapdien_mapped": 1,
                        "fused_candidates": 3,
                        "selected_candidates": 1,
                    },
                    "errors": {"dense": "timeout"},
                },
            },
            {
                "id": 2,
                "question": "Câu hỏi không có lỗi rõ ràng",
                "selected_articles": ["article-2", "article-3", "article-4"],
                "candidate_count": 8,
                "debug": {
                    "stage_counts": {
                        "bm25_legal": 4,
                        "dense_legal": 4,
                        "exact": 1,
                        "phapdien_mapped": 0,
                        "fused_candidates": 8,
                        "selected_candidates": 3,
                    },
                    "errors": {},
                },
            },
            {
                "id": 3,
                "question": "Thiếu debug vẫn không crash",
                "selected_articles": [],
            },
        ],
    )
    _write_jsonl(
        answers_path,
        [
            {
                "id": 1,
                "question": "Theo Điều 4 Luật hỗ trợ DNNVV thì sao?",
                "answer": "Căn cứ Điều",
                "selected_articles": [
                    {
                        "article_id": "article-1",
                        "law_id": "Không số",
                        "article_text": "",
                    }
                ],
            },
            {
                "id": 2,
                "question": "Câu hỏi không có lỗi rõ ràng",
                "answer": "Đây là câu trả lời có độ dài đủ lớn, nêu căn cứ pháp lý và kết luận sơ bộ cho câu hỏi.",
                "selected_articles": [
                    {
                        "article_id": "article-2",
                        "law_id": "01/2020/QH14",
                        "article_text": "Nội dung điều luật.",
                    },
                    {
                        "article_id": "article-3",
                        "law_id": "01/2020/QH14",
                        "article_text": "Nội dung điều luật.",
                    },
                    {
                        "article_id": "article-4",
                        "law_id": "01/2020/QH14",
                        "article_text": "Nội dung điều luật.",
                    },
                ],
            },
        ],
    )

    summary = build_error_analysis_report(
        retrieval_results_path=str(retrieval_path),
        generated_answers_path=str(answers_path),
        output_dir=str(output_dir),
    )

    assert summary["total_questions"] == 3
    assert summary["low_confidence_count"] >= 2

    low_confidence_path = output_dir / "low_confidence_questions.csv"
    debug_report_path = output_dir / "retrieval_debug_report.csv"
    assert low_confidence_path.exists()
    assert debug_report_path.exists()

    low_confidence_rows = _read_csv(low_confidence_path)
    debug_rows = _read_csv(debug_report_path)

    assert len(debug_rows) == 3
    first_issue_categories = low_confidence_rows[0]["issue_categories"]
    assert "answer_maybe_truncated" in first_issue_categories
    assert "empty_article_text" in first_issue_categories
    assert "retrieval_stage_error" in first_issue_categories


def test_build_error_analysis_report_includes_answer_only_ids(tmp_path: Path) -> None:
    retrieval_path = tmp_path / "retrieval_results.jsonl"
    answers_path = tmp_path / "generated_answers.jsonl"
    output_dir = tmp_path / "error_analysis"

    _write_jsonl(retrieval_path, [])
    _write_jsonl(
        answers_path,
        [
            {
                "id": "answer-only",
                "question": "Chỉ có ở generated answers",
                "answer": "",
                "selected_articles": [],
            }
        ],
    )

    summary = build_error_analysis_report(str(retrieval_path), str(answers_path), str(output_dir))
    debug_rows = _read_csv(output_dir / "retrieval_debug_report.csv")

    assert summary["total_questions"] == 1
    assert debug_rows[0]["id"] == "answer-only"
