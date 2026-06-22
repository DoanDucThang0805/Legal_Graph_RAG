import csv
import json

import pytest

from backend.evaluation.tightened_subset_regeneration import (
    build_changed_selected_articles_rows,
    extract_selected_article_ids,
    find_changed_selected_article_ids,
    merge_tightened_selector_subset,
    regenerate_tightened_selector_subset,
)


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = []

    def generate_answer(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "generated answer"


def test_find_changed_selected_article_ids_when_list_differs(tmp_path) -> None:
    baseline, tightened = _retrieval_pair(tmp_path, ["A|Law|1", "B|Law|2"], ["A|Law|1"])
    assert find_changed_selected_article_ids(baseline, tightened) == [1]


def test_unchanged_selected_articles_not_marked(tmp_path) -> None:
    baseline, tightened = _retrieval_pair(tmp_path, ["A|Law|1"], ["A|Law|1"])
    assert find_changed_selected_article_ids(baseline, tightened) == []


def test_compare_exact_order_and_content(tmp_path) -> None:
    baseline, tightened = _retrieval_pair(tmp_path, ["A|Law|1", "B|Law|2"], ["B|Law|2", "A|Law|1"])
    rows = build_changed_selected_articles_rows(baseline, tightened)
    assert len(rows) == 1
    assert rows[0]["selected_count_delta"] == 0


def test_changed_csv_rows_have_counts(tmp_path) -> None:
    baseline, tightened = _retrieval_pair(tmp_path, ["A|Law|1", "B|Law|2"], ["A|Law|1"])
    rows = build_changed_selected_articles_rows(baseline, tightened)
    assert rows[0]["baseline_selected_count"] == 2
    assert rows[0]["tightened_selected_count"] == 1
    assert rows[0]["baseline_unique_law_count"] == 2
    assert rows[0]["tightened_unique_law_count"] == 1


def test_extract_selected_article_ids_supports_dicts_and_strings() -> None:
    row = {"selected_articles": ["A|Law|1", {"article_id": "B|Law|2"}]}
    assert extract_selected_article_ids(row) == ["A|Law|1", "B|Law|2"]


def test_regeneration_uses_tightened_retrieval_row(tmp_path) -> None:
    baseline, tightened = _retrieval_pair(tmp_path, ["A|Law|1", "B|Law|2"], ["A|Law|1"])
    articles_path = _legal_articles_parquet(tmp_path, ["A|Law|1", "B|Law|2"])
    out = tmp_path / "out"
    summary = regenerate_tightened_selector_subset(
        baseline_retrieval_path=baseline,
        tightened_retrieval_path=tightened,
        output_dir=out,
        legal_articles_path=articles_path,
        generator=FakeGenerator(),
    )
    rows = _read_jsonl(out / "generated_answers_p6r6c_soft_10_7_subset.jsonl")
    assert summary["changed_count"] == 1
    assert len(rows) == 1
    assert len(rows[0]["selected_articles"]) == 1
    assert rows[0]["selected_articles"][0]["article_id"] == "A|Law|1"


def test_merge_preserves_base_row_count_and_replaces_subset(tmp_path) -> None:
    base = tmp_path / "base.jsonl"
    subset = tmp_path / "subset.jsonl"
    output = tmp_path / "merged.jsonl"
    _write_jsonl(base, [{"id": 1, "answer": "old"}, {"id": 2, "answer": "old2"}])
    _write_jsonl(subset, [{"id": 1, "answer": "new", "selected_articles": ["A|Law|1"]}])
    summary = merge_tightened_selector_subset(base, subset, output)
    rows = _read_jsonl(output)
    assert summary["output_rows"] == 2
    assert rows[0]["answer"] == "new"
    assert rows[1]["answer"] == "old2"


def test_merge_reports_duplicate_subset_ids(tmp_path) -> None:
    base = tmp_path / "base.jsonl"
    subset = tmp_path / "subset.jsonl"
    output = tmp_path / "merged.jsonl"
    _write_jsonl(base, [{"id": "a", "answer": "old"}])
    _write_jsonl(subset, [{"id": "a", "answer": "first"}, {"id": "a", "answer": "last"}])
    summary = merge_tightened_selector_subset(base, subset, output)
    assert summary["duplicate_subset_ids"] == ["a"]


def test_merge_missing_subset_id_raises(tmp_path) -> None:
    base = tmp_path / "base.jsonl"
    subset = tmp_path / "subset.jsonl"
    output = tmp_path / "merged.jsonl"
    _write_jsonl(base, [{"id": "a", "answer": "old"}])
    _write_jsonl(subset, [{"id": "missing", "answer": "new"}])
    with pytest.raises(ValueError, match="not present in base"):
        merge_tightened_selector_subset(base, subset, output)


def test_generated_answer_keeps_selected_articles_output_schema(tmp_path) -> None:
    baseline, tightened = _retrieval_pair(tmp_path, ["A|Law|1", "B|Law|2"], ["A|Law|1"])
    articles_path = _legal_articles_parquet(tmp_path, ["A|Law|1"])
    out = tmp_path / "out"
    regenerate_tightened_selector_subset(baseline, tightened, out, articles_path, FakeGenerator())
    rows = _read_jsonl(out / "generated_answers_p6r6c_soft_10_7_subset.jsonl")
    assert isinstance(rows[0]["selected_articles"], list)
    assert rows[0]["selected_articles"][0]["article_id"] == "A|Law|1"


def _retrieval_pair(tmp_path, baseline_articles, tightened_articles):
    baseline = tmp_path / "baseline.jsonl"
    tightened = tmp_path / "tightened.jsonl"
    _write_jsonl(baseline, [{"id": 1, "question": "Question", "selected_articles": baseline_articles}])
    _write_jsonl(tightened, [{"id": 1, "question": "Question", "selected_articles": tightened_articles}])
    return baseline, tightened


def _legal_articles_parquet(tmp_path, article_ids):
    import polars as pl

    rows = []
    for article_id in article_ids:
        law_id, law_title, article_no = article_id.split("|", 2)
        rows.append(
            {
                "article_id": article_id,
                "law_id": law_id,
                "law_title": law_title,
                "article_no": article_no,
                "article_title": "",
                "article_text": f"Text for {article_id}",
            }
        )
    path = tmp_path / "legal_articles.parquet"
    pl.DataFrame(rows).write_parquet(path)
    return path


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path):
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]

