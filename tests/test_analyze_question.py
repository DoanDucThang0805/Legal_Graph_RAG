import json

import polars as pl
import pytest

from backend.query_analysis.analyze_question import analyze_questions_dataframe, analyze_test_questions


def test_analyze_questions_dataframe_adds_query_analysis_columns() -> None:
    questions_df = pl.DataFrame(
        [
            {"id": 1, "question": "DNNVV được hỗ trợ trong bao nhiêu ngày theo Điều 4?"},
            {"id": 2, "question": "Công ty lập hóa đơn đỏ sai có bị phạt tiền không?"},
        ]
    )

    result = analyze_questions_dataframe(questions_df)

    assert result.shape == (2, 10)
    assert result["id"].to_list() == [1, 2]
    assert result["question"].to_list() == questions_df["question"].to_list()
    assert result["domain"].to_list() == ["sme_support", "tax_invoice"]
    assert result["answer_type"].to_list() == ["deadline", "sanction"]
    assert all(value in {"single_hop", "multi_hop"} for value in result["complexity"].to_list())


def test_analyze_questions_dataframe_serializes_json_columns() -> None:
    questions_df = pl.DataFrame([{"id": 1, "question": "Theo Điều 04, DNNVV có được hỗ trợ không?"}])

    row = analyze_questions_dataframe(questions_df).row(0, named=True)
    legal_entities = json.loads(row["legal_entities_json"])
    expanded_queries = json.loads(row["expanded_queries_json"])

    assert legal_entities["article_numbers"] == ["Điều 4"]
    assert expanded_queries[0] == "Theo Điều 04, DNNVV có được hỗ trợ không?"
    assert any("doanh nghiệp nhỏ và vừa" in query for query in expanded_queries)


def test_analyze_test_questions_reads_and_writes_parquet(tmp_path) -> None:
    input_path = tmp_path / "test_questions.parquet"
    output_path = tmp_path / "test_questions_analyzed.parquet"
    pl.DataFrame([{"id": 1, "question": "Hồ sơ đăng ký hộ kinh doanh gồm giấy tờ gì?"}]).write_parquet(input_path)

    result = analyze_test_questions(input_path, output_path)
    saved_df = pl.read_parquet(output_path)

    assert result.shape == saved_df.shape
    assert saved_df["domain"].to_list() == ["business_registration"]
    assert saved_df["answer_type"].to_list() == ["dossier"]


def test_analyze_questions_dataframe_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        analyze_questions_dataframe(pl.DataFrame([{"id": 1, "text": "Câu hỏi"}]))


def test_analyze_questions_dataframe_rejects_empty_dataframe() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        analyze_questions_dataframe(pl.DataFrame(schema={"id": pl.Int64, "question": pl.Utf8}))
