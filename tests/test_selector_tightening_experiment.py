import csv
import json

import pytest

from backend.evaluation.selector_tightening_experiment import (
    ArticleRef,
    SelectorTighteningConfig,
    build_summary,
    extract_selected_articles,
    is_explicit_multilaw_question,
    metadata_quality_penalty,
    parse_article_id,
    run_selector_tightening_experiment,
    set_selected_articles,
    tighten_selected_articles,
)


def test_parse_article_id_parses_canonical_string() -> None:
    article_id = "40/2021/TT-BTC|Thong tu 40/2021/TT-BTC|Dieu 5"
    ref = parse_article_id(article_id)
    assert ref == ArticleRef(article_id=article_id, law_id="40/2021/TT-BTC", law_title="Thong tu 40/2021/TT-BTC", article_no="Dieu 5")


def test_parse_article_id_handles_malformed_string() -> None:
    ref = parse_article_id("malformed")
    assert ref.article_id == "malformed"
    assert ref.law_id == ""
    assert ref.law_title == ""
    assert ref.article_no == ""


def test_extract_selected_articles_supports_string_items() -> None:
    row = {"selected_articles": ["LAW|Title|Article 1", "LAW|Title|Article 2"]}
    assert extract_selected_articles(row) == ["LAW|Title|Article 1", "LAW|Title|Article 2"]


def test_extract_selected_articles_supports_dict_items() -> None:
    row = {"selected_articles": [{"article_id": "LAW|Title|Article 1"}, {"missing": "ignored"}]}
    assert extract_selected_articles(row) == ["LAW|Title|Article 1"]


def test_set_selected_articles_writes_list_strings_without_mutating_original() -> None:
    row = {"id": 1, "selected_articles": ["old"]}
    updated = set_selected_articles(row, ["new"])
    assert updated["selected_articles"] == ["new"]
    assert row["selected_articles"] == ["old"]


def test_is_explicit_multilaw_question_detects_signals() -> None:
    assert is_explicit_multilaw_question("So s\u00e1nh quy \u0111\u1ecbnh theo c\u00e1c lu\u1eadt kh\u00e1c nhau") is True
    assert is_explicit_multilaw_question("H\u1ed9 kinh doanh k\u00ea khai thu\u1ebf th\u1ebf n\u00e0o?") is False


def test_metadata_quality_penalty_detects_article_ref_anomalies() -> None:
    assert metadata_quality_penalty(parse_article_id("Kh\u00f4ng s\u1ed1|Title|Article")) >= 2.0
    assert metadata_quality_penalty(parse_article_id("12/2022/ND-CP||Article")) >= 1.0
    assert metadata_quality_penalty(parse_article_id("80/2021/TT-BTC|Nghi dinh 02/2000/ND-CP|Article")) >= 1.5
    assert metadata_quality_penalty(parse_article_id("malformed")) >= 1.0


def test_tighten_selected_articles_never_adds_new_strings_and_respects_max_selected() -> None:
    articles = [_article_id(i, f"LAW{i}") for i in range(10)]
    tightened, _ = tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=5, max_unique_law_ids=5, min_keep=3))
    assert len(tightened) == 5
    assert set(tightened).issubset(set(articles))


def test_tighten_selected_articles_respects_min_keep() -> None:
    articles = [_article_id(i, f"LAW{i}") for i in range(5)]
    tightened, _ = tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=1, max_unique_law_ids=1, min_keep=3))
    assert len(tightened) >= 3


def test_tighten_selected_articles_reduces_unique_laws_for_non_multilaw() -> None:
    articles = [_article_id(i, f"LAW{i}") for i in range(8)]
    tightened, debug = tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=8, max_unique_law_ids=3, min_keep=3))
    assert len({parse_article_id(article_id).law_id for article_id in tightened}) <= 3
    assert debug["tightened_unique_law_count"] <= 3


def test_explicit_multilaw_question_preserves_broader_unique_laws() -> None:
    articles = [_article_id(i, f"LAW{i}") for i in range(8)]
    tightened, debug = tighten_selected_articles("So s\u00e1nh theo c\u00e1c lu\u1eadt kh\u00e1c nhau", articles, SelectorTighteningConfig(max_selected=8, max_unique_law_ids=3, min_keep=3, preserve_explicit_multilaw=True))
    assert len({parse_article_id(article_id).law_id for article_id in tightened}) == 8
    assert debug["explicit_multilaw_question"] is True


def test_tighten_selected_articles_does_not_mutate_original_list() -> None:
    articles = [_article_id(i, "LAW") for i in range(5)]
    original = list(articles)
    tighten_selected_articles("ordinary question", articles, SelectorTighteningConfig(max_selected=3))
    assert articles == original


def test_build_summary_distributions_and_p6r5_consistency() -> None:
    rows = [
        {"id": "1", "original_selected_count": 12, "tightened_selected_count": 8, "original_unique_law_count": 10, "tightened_unique_law_count": 5, "selected_count_delta": 4, "unique_law_count_delta": 5, "risk_flag": "none", "explicit_multilaw_question": False, "is_too_many_selected_case": True},
        {"id": "2", "original_selected_count": 3, "tightened_selected_count": 3, "original_unique_law_count": 1, "tightened_unique_law_count": 1, "selected_count_delta": 0, "unique_law_count_delta": 0, "risk_flag": "none", "explicit_multilaw_question": False, "is_too_many_selected_case": False},
    ]
    summary = build_summary(rows, SelectorTighteningConfig(), [{}, {}], {"1"}, rows_with_selected=2, selected_item_type="str")
    assert summary["baseline_selected_count_distribution"] == {"3": 1, "12": 1}
    assert summary["tightened_selected_count_distribution"] == {"3": 1, "8": 1}
    assert summary["p6r5_too_many_cases_checked"] == 1
    assert summary["p6r5_too_many_cases_with_original_count_12"] == 1


def test_build_summary_warns_when_p6r5_count_is_not_12() -> None:
    rows = [{"id": "1", "original_selected_count": 8, "tightened_selected_count": 8, "original_unique_law_count": 2, "tightened_unique_law_count": 2, "selected_count_delta": 0, "unique_law_count_delta": 0, "risk_flag": "none", "explicit_multilaw_question": False, "is_too_many_selected_case": True}]
    summary = build_summary(rows, SelectorTighteningConfig(), [{}], {"1"}, rows_with_selected=1, selected_item_type="str")
    assert summary["p6r5_too_many_cases_with_original_count_12"] == 0
    assert summary["warnings"]


def test_runtime_output_keeps_selected_articles_as_list_strings(tmp_path) -> None:
    retrieval = tmp_path / "retrieval.jsonl"
    low = tmp_path / "low.csv"
    p6r5 = tmp_path / "p6r5.csv"
    p6r5b = tmp_path / "p6r5b.json"
    rules = tmp_path / "rules.json"
    out = tmp_path / "out"
    _write_jsonl(retrieval, [{"id": 1, "question": "ordinary question", "selected_articles": [_article_id(i, f"LAW{i}") for i in range(12)]}])
    _write_csv(low, ["id", "issue_categories"], [{"id": "1", "issue_categories": "too_many_selected_articles"}])
    _write_csv(p6r5, ["id"], [{"id": "1"}])
    p6r5b.write_text("{}", encoding="utf-8")
    rules.write_text("[]", encoding="utf-8")
    summary = run_selector_tightening_experiment(retrieval, low, p6r5, p6r5b, rules, out, SelectorTighteningConfig(max_selected=8, max_unique_law_ids=5))
    rows = _read_jsonl(out / "retrieval_results_p6r6_tightened.jsonl")
    assert summary["selected_article_item_type"] == "str"
    assert summary["rows_with_selected_articles"] == 1
    assert isinstance(rows[0]["selected_articles"][0], str)
    assert len(rows[0]["selected_articles"]) == 5
    assert len({parse_article_id(article_id).law_id for article_id in rows[0]["selected_articles"]}) <= 5


def test_runtime_fails_fast_when_no_selected_articles(tmp_path) -> None:
    retrieval = tmp_path / "retrieval.jsonl"
    low = tmp_path / "low.csv"
    p6r5 = tmp_path / "p6r5.csv"
    p6r5b = tmp_path / "p6r5b.json"
    rules = tmp_path / "rules.json"
    _write_jsonl(retrieval, [{"id": 1, "question": "ordinary question", "selected_articles": []}])
    _write_csv(low, ["id", "issue_categories"], [])
    _write_csv(p6r5, ["id"], [])
    p6r5b.write_text("{}", encoding="utf-8")
    rules.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="No selected articles found"):
        run_selector_tightening_experiment(retrieval, low, p6r5, p6r5b, rules, tmp_path / "out")


def _article_id(index: int, law_id: str) -> str:
    return f"{law_id}|Law title|Article {index}"


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path):
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _write_csv(path, columns, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
