import json

import polars as pl
import pytest

from backend.knowledge_processing.load_testset import load_test_questions


def test_load_test_questions_writes_parquet(tmp_path) -> None:
    input_path = tmp_path / "R2AIStage1DATA.json"
    output_path = tmp_path / "test_questions.parquet"
    input_path.write_text(
        json.dumps(
            [
                {"id": "1", "question": "  Doanh\u00a0nghiệp   nhỏ là gì?  "},
                {"id": 2, "question": "Điều kiện hỗ trợ DNNVV?"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    df = load_test_questions(input_path, output_path)
    saved_df = pl.read_parquet(output_path)

    assert df.shape == (2, 2)
    assert saved_df.to_dicts() == [
        {"id": 1, "question": "Doanh nghiệp nhỏ là gì?"},
        {"id": 2, "question": "Điều kiện hỗ trợ DNNVV?"},
    ]


def test_load_test_questions_rejects_non_list_json(tmp_path) -> None:
    input_path = tmp_path / "R2AIStage1DATA.json"
    output_path = tmp_path / "test_questions.parquet"
    input_path.write_text(json.dumps({"id": 1, "question": "Sai format"}), encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a list"):
        load_test_questions(input_path, output_path)


def test_load_test_questions_rejects_duplicate_id(tmp_path) -> None:
    input_path = tmp_path / "R2AIStage1DATA.json"
    output_path = tmp_path / "test_questions.parquet"
    input_path.write_text(
        json.dumps(
            [
                {"id": 1, "question": "Câu hỏi 1"},
                {"id": "1", "question": "Câu hỏi trùng"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid testset rows"):
        load_test_questions(input_path, output_path)


def test_load_test_questions_rejects_empty_question(tmp_path) -> None:
    input_path = tmp_path / "R2AIStage1DATA.json"
    output_path = tmp_path / "test_questions.parquet"
    input_path.write_text(json.dumps([{"id": 1, "question": "   "}]), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid testset rows"):
        load_test_questions(input_path, output_path)


def test_load_test_questions_rejects_invalid_id(tmp_path) -> None:
    input_path = tmp_path / "R2AIStage1DATA.json"
    output_path = tmp_path / "test_questions.parquet"
    input_path.write_text(json.dumps([{"id": "abc", "question": "Câu hỏi"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid testset rows"):
        load_test_questions(input_path, output_path)
