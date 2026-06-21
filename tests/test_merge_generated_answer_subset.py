import json

import pytest

from backend.evaluation.generated_answer_merge import merge_generated_answer_subset


def test_merge_generated_answer_subset_preserves_row_count_and_replaces_by_id(tmp_path) -> None:
    base_path = tmp_path / "base.jsonl"
    subset_path = tmp_path / "subset.jsonl"
    output_path = tmp_path / "merged.jsonl"
    _write_jsonl(
        base_path,
        [
            {"id": 1, "answer": "old 1"},
            {"id": 2, "answer": "old 2"},
            {"id": 3, "answer": "old 3"},
        ],
    )
    _write_jsonl(subset_path, [{"id": 2, "answer": "new 2"}])

    summary = merge_generated_answer_subset(base_path, subset_path, output_path)

    merged = _read_jsonl(output_path)
    assert summary["base_rows"] == 3
    assert summary["subset_rows"] == 1
    assert summary["output_rows"] == 3
    assert summary["replaced"] == 1
    assert [row["id"] for row in merged] == [1, 2, 3]
    assert merged[1]["answer"] == "new 2"


def test_merge_generated_answer_subset_uses_last_duplicate_subset_id(tmp_path) -> None:
    base_path = tmp_path / "base.jsonl"
    subset_path = tmp_path / "subset.jsonl"
    output_path = tmp_path / "merged.jsonl"
    _write_jsonl(base_path, [{"id": "a", "answer": "old"}])
    _write_jsonl(
        subset_path,
        [
            {"id": "a", "answer": "new first"},
            {"id": "a", "answer": "new last"},
        ],
    )

    summary = merge_generated_answer_subset(base_path, subset_path, output_path)

    merged = _read_jsonl(output_path)
    assert summary["output_rows"] == 1
    assert summary["replaced"] == 1
    assert summary["duplicate_subset_ids"] == ["a"]
    assert merged == [{"id": "a", "answer": "new last"}]


def test_merge_generated_answer_subset_rejects_subset_id_missing_from_base(tmp_path) -> None:
    base_path = tmp_path / "base.jsonl"
    subset_path = tmp_path / "subset.jsonl"
    output_path = tmp_path / "merged.jsonl"
    _write_jsonl(base_path, [{"id": "a", "answer": "old"}])
    _write_jsonl(subset_path, [{"id": "b", "answer": "new"}])

    with pytest.raises(ValueError, match="not present in base"):
        merge_generated_answer_subset(base_path, subset_path, output_path)


def _write_jsonl(path, rows) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path):
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]
