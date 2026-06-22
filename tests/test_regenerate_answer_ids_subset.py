import csv
import json

from backend.evaluation.subset_answer_regeneration import generate_answer_ids_subset, read_question_ids_csv


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = []

    def generate_answer(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return f"generated answer for {kwargs['question']}"


def test_reads_ids_csv_and_filters_correct_retrieval_rows(tmp_path) -> None:
    ids_csv = tmp_path / "ids.csv"
    retrieval = tmp_path / "retrieval.jsonl"
    output = tmp_path / "subset.jsonl"
    articles_path = _legal_articles_parquet(tmp_path, ["LAW|Law title|Article 1", "LAW|Law title|Article 3"])
    _write_csv(ids_csv, ["id", "question", "issue_categories"], [{"id": "1", "question": "Q1", "issue_categories": "answer_maybe_truncated"}, {"id": "3", "question": "Q3", "issue_categories": "answer_maybe_truncated"}])
    _write_jsonl(
        retrieval,
        [
            {"id": 1, "question": "Q1", "selected_articles": ["LAW|Law title|Article 1"]},
            {"id": 2, "question": "Q2", "selected_articles": ["LAW|Law title|Article 2"]},
            {"id": 3, "question": "Q3", "selected_articles": ["LAW|Law title|Article 3"]},
        ],
    )
    generator = FakeGenerator()

    summary = generate_answer_ids_subset(ids_csv, retrieval, output, articles_path, generator)
    rows = _read_jsonl(output)

    assert summary["requested"] == 2
    assert summary["processed"] == 2
    assert [row["id"] for row in rows] == [1, 3]
    assert [call["question"] for call in generator.calls] == ["Q1", "Q3"]


def test_missing_ids_are_reported_in_summary(tmp_path) -> None:
    ids_csv = tmp_path / "ids.csv"
    retrieval = tmp_path / "retrieval.jsonl"
    output = tmp_path / "subset.jsonl"
    articles_path = _legal_articles_parquet(tmp_path, ["LAW|Law title|Article 1"])
    _write_csv(ids_csv, ["id"], [{"id": "1"}, {"id": "99"}])
    _write_jsonl(retrieval, [{"id": 1, "question": "Q1", "selected_articles": ["LAW|Law title|Article 1"]}])

    summary = generate_answer_ids_subset(ids_csv, retrieval, output, articles_path, FakeGenerator())
    saved_summary = json.loads((tmp_path / "regeneration_summary.json").read_text(encoding="utf-8"))

    assert summary["missing"] == 1
    assert summary["missing_ids"] == ["99"]
    assert saved_summary["missing_ids"] == ["99"]
    assert saved_summary["ids_csv_path"] == str(ids_csv)
    assert saved_summary["retrieval_results_path"] == str(retrieval)
    assert saved_summary["output_path"] == str(output)


def test_output_jsonl_has_one_row_per_processed_id(tmp_path) -> None:
    ids_csv, retrieval, articles_path = _basic_inputs(tmp_path)
    output = tmp_path / "subset.jsonl"

    summary = generate_answer_ids_subset(ids_csv, retrieval, output, articles_path, FakeGenerator())
    rows = _read_jsonl(output)

    assert summary["processed"] == 1
    assert len(rows) == 1


def test_output_schema_remains_merge_compatible(tmp_path) -> None:
    ids_csv, retrieval, articles_path = _basic_inputs(tmp_path)
    output = tmp_path / "subset.jsonl"

    generate_answer_ids_subset(ids_csv, retrieval, output, articles_path, FakeGenerator())
    row = _read_jsonl(output)[0]

    assert set(row) == {"id", "question", "answer", "selected_articles"}
    assert row["id"] == 1
    assert row["answer"].startswith("generated answer")
    assert isinstance(row["selected_articles"], list)
    assert row["selected_articles"][0]["article_id"] == "LAW|Law title|Article 1"
    assert row["selected_articles"][0]["article_text"]


def test_does_not_regenerate_ids_not_in_csv(tmp_path) -> None:
    ids_csv, retrieval, articles_path = _basic_inputs(tmp_path)
    output = tmp_path / "subset.jsonl"
    generator = FakeGenerator()

    generate_answer_ids_subset(ids_csv, retrieval, output, articles_path, generator)

    assert [call["question"] for call in generator.calls] == ["Q1"]
    assert [row["id"] for row in _read_jsonl(output)] == [1]


def test_read_question_ids_csv_supports_custom_id_column(tmp_path) -> None:
    ids_csv = tmp_path / "ids.csv"
    _write_csv(ids_csv, ["question_id"], [{"question_id": "1"}, {"question_id": "1"}, {"question_id": "2"}])

    assert read_question_ids_csv(ids_csv, id_column="question_id") == ["1", "2"]


def _basic_inputs(tmp_path):
    ids_csv = tmp_path / "ids.csv"
    retrieval = tmp_path / "retrieval.jsonl"
    articles_path = _legal_articles_parquet(tmp_path, ["LAW|Law title|Article 1"])
    _write_csv(ids_csv, ["id"], [{"id": "1"}])
    _write_jsonl(
        retrieval,
        [
            {"id": 1, "question": "Q1", "selected_articles": ["LAW|Law title|Article 1"]},
            {"id": 2, "question": "Q2", "selected_articles": ["LAW|Law title|Article 2"]},
        ],
    )
    return ids_csv, retrieval, articles_path


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
