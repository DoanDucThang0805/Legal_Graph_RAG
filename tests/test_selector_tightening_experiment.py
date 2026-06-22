import csv
import json

from backend.evaluation.selector_tightening_experiment import (
    SelectorTighteningConfig,
    build_summary,
    is_explicit_multilaw_question,
    metadata_quality_penalty,
    run_selector_tightening_experiment,
    tighten_selected_articles,
)


def test_is_explicit_multilaw_question_detects_signals() -> None:
    assert is_explicit_multilaw_question("So s\u00e1nh quy \u0111\u1ecbnh theo c\u00e1c lu\u1eadt kh\u00e1c nhau") is True
    assert is_explicit_multilaw_question("H\u1ed9 kinh doanh k\u00ea khai thu\u1ebf th\u1ebf n\u00e0o?") is False


def test_metadata_quality_penalty_detects_anomalies() -> None:
    assert metadata_quality_penalty({"law_id": "Kh\u00f4ng s\u1ed1", "law_title": "Title", "article_id": "a|b|c"}) >= 2.0
    assert metadata_quality_penalty({"law_id": "12/2022/ND-CP", "law_title": "", "article_id": "a|b|c"}) >= 1.0
    assert metadata_quality_penalty({"law_id": "80/2021/TT-BTC", "law_title": "Nghi dinh 02/2000/ND-CP", "article_id": "a|b|c"}) >= 1.5


def test_tighten_selected_articles_never_adds_new_articles_and_respects_max_selected() -> None:
    articles = [_article(i, f"LAW{i}") for i in range(10)]
    tightened, _ = tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=5, max_unique_law_ids=5, min_keep=3))
    assert len(tightened) == 5
    assert {a["article_id"] for a in tightened}.issubset({a["article_id"] for a in articles})


def test_tighten_selected_articles_respects_min_keep() -> None:
    articles = [_article(i, f"LAW{i}") for i in range(5)]
    tightened, _ = tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=1, max_unique_law_ids=1, min_keep=3))
    assert len(tightened) >= 3


def test_tighten_selected_articles_reduces_unique_laws_for_non_multilaw() -> None:
    articles = [_article(i, f"LAW{i}") for i in range(8)]
    tightened, debug = tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=8, max_unique_law_ids=3, min_keep=3))
    assert len({a["law_id"] for a in tightened}) <= 3
    assert debug["tightened_unique_law_count"] <= 3


def test_explicit_multilaw_question_preserves_broader_unique_laws() -> None:
    articles = [_article(i, f"LAW{i}") for i in range(8)]
    tightened, debug = tighten_selected_articles("So s\u00e1nh theo c\u00e1c lu\u1eadt kh\u00e1c nhau", articles, SelectorTighteningConfig(max_selected=8, max_unique_law_ids=3, min_keep=3, preserve_explicit_multilaw=True))
    assert len({a["law_id"] for a in tightened}) == 8
    assert debug["explicit_multilaw_question"] is True


def test_tighten_selected_articles_does_not_mutate_original_objects() -> None:
    articles = [_article(i, "LAW") for i in range(5)]
    original = json.loads(json.dumps(articles, ensure_ascii=False))
    tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=3))
    assert articles == original


def test_build_summary_distributions_are_computed() -> None:
    rows = [
        {"original_selected_count": 12, "tightened_selected_count": 8, "original_unique_law_count": 10, "tightened_unique_law_count": 5, "selected_count_delta": 4, "unique_law_count_delta": 5, "risk_flag": "none", "explicit_multilaw_question": False, "is_too_many_selected_case": True},
        {"original_selected_count": 3, "tightened_selected_count": 3, "original_unique_law_count": 1, "tightened_unique_law_count": 1, "selected_count_delta": 0, "unique_law_count_delta": 0, "risk_flag": "none", "explicit_multilaw_question": False, "is_too_many_selected_case": False},
    ]
    summary = build_summary(rows, SelectorTighteningConfig(), [{}, {}], {"1"})
    assert summary["baseline_selected_count_distribution"] == {"3": 1, "12": 1}
    assert summary["tightened_selected_count_distribution"] == {"3": 1, "8": 1}
    assert summary["cases_reduced_selected_count"] == 1


def test_runtime_report_handles_missing_scores_and_writes_outputs(tmp_path) -> None:
    retrieval = tmp_path / "retrieval.jsonl"
    low = tmp_path / "low.csv"
    p6r5 = tmp_path / "p6r5.csv"
    p6r5b = tmp_path / "p6r5b.json"
    rules = tmp_path / "rules.json"
    out = tmp_path / "out"
    _write_jsonl(retrieval, [{"id": 1, "question": "ordinary question", "selected_articles": [_article(i, f"LAW{i}") for i in range(12)]}])
    _write_csv(low, ["id", "issue_categories"], [{"id": "1", "issue_categories": "too_many_selected_articles"}])
    _write_csv(p6r5, ["id"], [{"id": "1"}])
    p6r5b.write_text("{}", encoding="utf-8")
    rules.write_text("[]", encoding="utf-8")
    summary = run_selector_tightening_experiment(retrieval, low, p6r5, p6r5b, rules, out, SelectorTighteningConfig(max_selected=8, max_unique_law_ids=5))
    assert summary["retrieval_rows"] == 1
    assert (out / "retrieval_results_p6r6_tightened.jsonl").exists()
    assert (out / "selector_tightening_report.csv").exists()
    assert (out / "selector_tightening_summary.json").exists()
    assert (out / "selector_tightening_samples.md").exists()


def _article(index: int, law_id: str) -> dict[str, object]:
    return {"article_id": f"{law_id}|Law title|Article {index}", "law_id": law_id, "law_title": "Law title", "article_no": f"Article {index}"}


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path, columns, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
