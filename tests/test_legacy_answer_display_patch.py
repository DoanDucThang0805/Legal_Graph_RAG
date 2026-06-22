import csv
import json

from backend.evaluation.legacy_answer_display_patch import (
    cleanup_spacing_preserve_lines,
    patch_legacy_answer_display,
    run_legacy_answer_display_patch,
)


def test_patch_bo_luat_lao_dong_so_khong_so() -> None:
    answer = "\u0110i\u1ec1u 71 c\u1ee7a B\u1ed9 lu\u1eadt Lao \u0111\u1ed9ng s\u1ed1 Kh\u00f4ng s\u1ed1 quy \u0111\u1ecbnh v\u1ec1 ngh\u1ec9 ph\u00e9p."

    patched, notes = patch_legacy_answer_display(answer)

    assert "Kh\u00f4ng s\u1ed1" not in patched
    assert "B\u1ed9 lu\u1eadt Lao \u0111\u1ed9ng quy \u0111\u1ecbnh" in patched
    assert "removed_so_khong_so" in notes


def test_patch_phap_lenh_khong_so_prefix() -> None:
    answer = "Ph\u00e1p l\u1ec7nh Kh\u00f4ng s\u1ed1 X\u1eed l\u00fd vi ph\u1ea1m h\u00e0nh ch\u00ednh quy \u0111\u1ecbnh th\u1ea9m quy\u1ec1n."

    patched, notes = patch_legacy_answer_display(answer)

    assert patched == "Ph\u00e1p l\u1ec7nh X\u1eed l\u00fd vi ph\u1ea1m h\u00e0nh ch\u00ednh quy \u0111\u1ecbnh th\u1ea9m quy\u1ec1n."
    assert "removed_prefix_khong_so" in notes


def test_patch_does_not_delete_article_number() -> None:
    answer = "\u0110i\u1ec1u 71 c\u1ee7a B\u1ed9 lu\u1eadt Lao \u0111\u1ed9ng s\u1ed1 Kh\u00f4ng s\u1ed1."

    patched, _ = patch_legacy_answer_display(answer)

    assert "\u0110i\u1ec1u 71" in patched


def test_cleanup_double_spaces() -> None:
    text = "A  B   , C\n-  D   ."

    assert cleanup_spacing_preserve_lines(text) == "A B, C\n- D."


def test_non_target_row_is_not_patched(tmp_path) -> None:
    report, answers = _write_inputs(
        tmp_path,
        report_rows=[{"id": "1", "recommended_action": "manual_review_needed"}],
        answer_rows=[{"id": 1, "question": "Q1", "answer": "Lu\u1eadt Kh\u00f4ng s\u1ed1 Doanh nghi\u1ec7p."}],
    )

    run_legacy_answer_display_patch(report, answers, tmp_path / "out")
    rows = _read_jsonl(tmp_path / "out" / "generated_answers_p6r8_legacy_display_patch.jsonl")

    assert rows[0]["answer"] == "Lu\u1eadt Kh\u00f4ng s\u1ed1 Doanh nghi\u1ec7p."


def test_output_preserves_row_count_and_non_target_answer(tmp_path) -> None:
    report, answers = _write_inputs(
        tmp_path,
        report_rows=[{"id": "1", "recommended_action": "answer_patch_possible"}],
        answer_rows=[
            {"id": 1, "question": "Q1", "answer": "Lu\u1eadt Kh\u00f4ng s\u1ed1 Doanh nghi\u1ec7p."},
            {"id": 2, "question": "Q2", "answer": "Answer unchanged."},
        ],
    )

    run_legacy_answer_display_patch(report, answers, tmp_path / "out")
    rows = _read_jsonl(tmp_path / "out" / "generated_answers_p6r8_legacy_display_patch.jsonl")

    assert len(rows) == 2
    assert rows[0]["answer"] == "Lu\u1eadt Doanh nghi\u1ec7p."
    assert rows[1]["answer"] == "Answer unchanged."


def test_summary_counts_are_computed_correctly(tmp_path) -> None:
    report, answers = _write_inputs(
        tmp_path,
        report_rows=[
            {"id": "1", "recommended_action": "answer_patch_possible"},
            {"id": "2", "recommended_action": "answer_patch_possible"},
            {"id": "3", "recommended_action": "manual_review_needed"},
        ],
        answer_rows=[
            {"id": 1, "question": "Q1", "answer": "B\u1ed9 lu\u1eadt Kh\u00f4ng s\u1ed1 Lao \u0111\u1ed9ng."},
            {"id": 2, "question": "Q2", "answer": "Answer without marker."},
            {"id": 3, "question": "Q3", "answer": "Lu\u1eadt Kh\u00f4ng s\u1ed1 ignored."},
        ],
    )

    summary = run_legacy_answer_display_patch(report, answers, tmp_path / "out")

    assert summary["total_answers"] == 3
    assert summary["target_patch_ids"] == 2
    assert summary["patched_count"] == 1
    assert summary["before_contains_khong_so_count"] == 1
    assert summary["after_contains_khong_so_count"] == 0
    assert summary["unchanged_target_count"] == 1
    assert summary["non_target_changed_count"] == 0


def test_report_has_patch_status(tmp_path) -> None:
    report, answers = _write_inputs(
        tmp_path,
        report_rows=[{"id": "1", "recommended_action": "answer_patch_possible"}],
        answer_rows=[{"id": 1, "question": "Q1", "answer": "s\u1ed1 Kh\u00f4ng s\u1ed1."}],
    )

    run_legacy_answer_display_patch(report, answers, tmp_path / "out")
    rows = _read_csv(tmp_path / "out" / "legacy_answer_patch_report.csv")

    assert rows[0]["patched"] == "True"
    assert rows[0]["before_contains_khong_so"] == "True"
    assert rows[0]["after_contains_khong_so"] == "False"


def _write_inputs(tmp_path, report_rows, answer_rows):
    report = tmp_path / "p6r7.csv"
    answers = tmp_path / "answers.jsonl"
    _write_csv(report, ["id", "recommended_action"], report_rows)
    _write_jsonl(answers, answer_rows)
    return report, answers


def _write_csv(path, columns, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path):
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]
