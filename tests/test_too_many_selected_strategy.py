import csv
import json

from backend.evaluation.too_many_selected_strategy import (
    REQUIRED_RULE_FIELDS,
    build_candidate_selector_rules,
    build_high_noise_sample_review,
    build_too_many_selected_strategy,
    detect_metadata_anomalies,
    recommend_next_task,
    validate_summary_consistency,
)


def test_validate_summary_consistency_detects_mismatch() -> None:
    validation = validate_summary_consistency(
        [{"id": "1"}],
        {
            "total_too_many_selected_cases": 2,
            "category_counts": {"cross_law_possible_noise": 1},
            "selected_count_distribution": {"12": 1},
        },
    )
    assert validation["is_consistent"] is False
    assert validation["warnings"]


def test_detect_metadata_anomalies_catches_expected_types() -> None:
    rows = [
        {"id": "1", "unique_law_ids": "12/2022/ND-CP;Khong so;80/2021/TT-BTC", "unique_law_titles_preview": ";Bo luat Dan su so Khong so;Nghi dinh 02/2000/ND-CP"},
    ]
    anomalies = detect_metadata_anomalies(rows, [])
    types = {(row["law_id"], row["anomaly_type"]) for row in anomalies}
    assert ("12/2022/ND-CP", "empty_law_title") in types
    assert ("Khong so", "unknown_law_id") in types
    assert ("80/2021/TT-BTC", "law_id_title_mismatch_suspected") in types


def test_candidate_rules_contain_required_fields() -> None:
    rules = build_candidate_selector_rules()
    assert rules
    for rule in rules:
        assert set(REQUIRED_RULE_FIELDS).issubset(rule)


def test_recommended_next_task_selector_tightening_when_cross_law_dominates_and_all_at_cap() -> None:
    summary = {"total_too_many_selected_cases": 216, "category_counts": {"cross_law_possible_noise": 174}, "selected_count_distribution": {"12": 216}}
    validation = validate_summary_consistency([{"id": str(i)} for i in range(216)], summary)
    decision = recommend_next_task(summary, validation)
    assert decision["recommended_next_task"] == "P6.R6_selector_tightening_experiment"


def test_sample_review_prioritizes_high_unique_law_count() -> None:
    rows = [
        _row("low", "cross_law_possible_noise", 5),
        _row("high", "cross_law_possible_noise", 11),
        _row("legacy", "legacy_or_version_noise", 8),
    ]
    review = build_high_noise_sample_review(rows)
    assert review[0]["id"] == "high"
    assert review[0]["manual_review_priority"] == "high"


def test_build_strategy_handles_missing_optional_generated_answers(tmp_path) -> None:
    report = tmp_path / "report.csv"
    summary = tmp_path / "summary.json"
    law_dist = tmp_path / "law.csv"
    samples = tmp_path / "samples.md"
    out = tmp_path / "out"
    _write_csv(report, ["id", "question", "heuristic_category", "selected_count", "unique_law_count", "unique_law_ids", "selected_article_ids_preview", "answer_preview"], [_row("1", "cross_law_possible_noise", 12)])
    summary.write_text(json.dumps({"total_too_many_selected_cases": 1, "category_counts": {"cross_law_possible_noise": 1}, "selected_count_distribution": {"12": 1}}), encoding="utf-8")
    _write_csv(law_dist, ["law_id", "law_title", "case_count", "article_count", "example_ids"], [{"law_id": "36/2005/QH11", "law_title": "Law", "case_count": "1", "article_count": "1", "example_ids": "1"}])
    samples.write_text("# samples", encoding="utf-8")

    result = build_too_many_selected_strategy(report, summary, law_dist, samples, out, generated_answers_path=tmp_path / "missing.jsonl")

    assert result["p6r5b_status"] == "completed"
    assert result["answer_record_count"] == 0
    assert (out / "too_many_selected_strategy_report.md").exists()
    assert (out / "candidate_selector_rules.json").exists()
    assert (out / "law_metadata_anomalies.csv").exists()
    assert (out / "high_noise_sample_review.csv").exists()


def _row(row_id: str, category: str, unique_law_count: int) -> dict[str, object]:
    law_ids = ";".join(f"LAW{i}" for i in range(unique_law_count))
    return {
        "id": row_id,
        "question": "Question about doanh nghiep and thue",
        "heuristic_category": category,
        "selected_count": 12,
        "unique_law_count": unique_law_count,
        "unique_law_ids": law_ids,
        "selected_article_ids_preview": "a;b;c",
        "answer_preview": "preview",
    }


def _write_csv(path, columns, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
