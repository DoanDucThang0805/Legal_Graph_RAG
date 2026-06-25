import json
from pathlib import Path

import polars as pl

from backend.evaluation.build_reranker_training_data import build_reranker_training_data


ARTICLE_A = "LAW-A|Luật A|Điều 1"
ARTICLE_B = "LAW-B|Luật B|Điều 2"
ARTICLE_C = "LAW-C|Luật C|Điều 3"
ARTICLE_D = "LAW-D|Luật D|Điều 4"


def test_import_module_success() -> None:
    assert callable(build_reranker_training_data)


def test_builds_sample_when_positive_and_negatives_are_valid(tmp_path: Path) -> None:
    legal_articles_path = _write_legal_articles(tmp_path)
    retrieval_path = _write_jsonl(
        tmp_path / "retrieval.jsonl",
        [
            {
                "id": 1,
                "question": "Câu hỏi A?",
                "selected_articles": [{"article_id": ARTICLE_A, "rank": 2, "score": 0.91}],
                "candidates": [
                    {"article_id": ARTICLE_A, "score": 0.91},
                    {"article_id": ARTICLE_B, "score": 0.8},
                    {"article_id": ARTICLE_C, "score": 0.7},
                ],
            }
        ],
    )
    output_path = tmp_path / "reranker_training_data.jsonl"
    summary_path = tmp_path / "summary.json"

    summary = build_reranker_training_data(
        retrieval_path,
        legal_articles_path,
        output_path,
        summary_path,
    )

    rows = _read_jsonl(output_path)
    assert summary["samples_written"] == 1
    assert summary["weak_label"] is True
    assert summary["dataset_type"] == "weak_supervision"
    assert rows == [
        {
            "question_id": "1",
            "query": "Câu hỏi A?",
            "positive_article_id": ARTICLE_A,
            "hard_negative_article_ids": [ARTICLE_B, ARTICLE_C],
            "weak_label": True,
            "label_source": "retrieval_selected_articles",
            "metadata": {
                "positive_rank": 2,
                "positive_score": 0.91,
                "num_candidates": 3,
                "num_hard_negatives": 2,
            },
        }
    ]


def test_skips_when_positive_article_id_is_not_canonical(tmp_path: Path) -> None:
    legal_articles_path = _write_legal_articles(tmp_path)
    retrieval_path = _write_jsonl(
        tmp_path / "retrieval.jsonl",
        [
            {
                "id": 2,
                "question": "Câu hỏi B?",
                "selected_article_ids": ["NOT-CANONICAL|Luật X|Điều 9"],
                "candidates": [{"article_id": ARTICLE_B}],
            }
        ],
    )
    output_path = tmp_path / "out.jsonl"
    summary_path = tmp_path / "summary.json"

    summary = build_reranker_training_data(retrieval_path, legal_articles_path, output_path, summary_path)

    assert _read_jsonl(output_path) == []
    assert summary["samples_written"] == 0
    assert summary["questions_skipped_invalid_positive"] == 1
    assert summary["invalid_positive_article_ids"] == ["NOT-CANONICAL|Luật X|Điều 9"]


def test_does_not_use_chunk_id_as_label(tmp_path: Path) -> None:
    legal_articles_path = _write_legal_articles(tmp_path)
    retrieval_path = _write_jsonl(
        tmp_path / "retrieval.jsonl",
        [
            {
                "id": 3,
                "question": "Câu hỏi C?",
                "selected_articles": [{"chunk_id": "chunk-1"}],
                "candidates": [
                    {"chunk_id": "chunk-1", "metadata": {"article_id": ARTICLE_A}},
                    {"article_id": ARTICLE_B},
                ],
            }
        ],
    )
    output_path = tmp_path / "out.jsonl"
    summary_path = tmp_path / "summary.json"

    summary = build_reranker_training_data(retrieval_path, legal_articles_path, output_path, summary_path)

    assert _read_jsonl(output_path) == []
    assert summary["questions_skipped_no_positive"] == 1
    assert summary["samples_written"] == 0


def test_chunk_level_hit_is_used_only_when_mapped_to_canonical_article_id(tmp_path: Path) -> None:
    legal_articles_path = _write_legal_articles(tmp_path)
    retrieval_path = _write_jsonl(
        tmp_path / "retrieval.jsonl",
        [
            {
                "id": 4,
                "query": "Câu hỏi D?",
                "selected_article_ids": [ARTICLE_A],
                "hits": [
                    {"chunk_id": "chunk-a", "metadata": {"article_id": ARTICLE_A}},
                    {"chunk_id": "chunk-b", "metadata": {"parent_article_id": ARTICLE_B}},
                    {"chunk_id": "chunk-c"},
                ],
            }
        ],
    )
    output_path = tmp_path / "out.jsonl"
    summary_path = tmp_path / "summary.json"

    build_reranker_training_data(retrieval_path, legal_articles_path, output_path, summary_path)

    rows = _read_jsonl(output_path)
    assert rows[0]["positive_article_id"] == ARTICLE_A
    assert rows[0]["hard_negative_article_ids"] == [ARTICLE_B]


def test_hard_negatives_are_deduplicated_exclude_positive_and_respect_limit(tmp_path: Path) -> None:
    legal_articles_path = _write_legal_articles(tmp_path)
    retrieval_path = _write_jsonl(
        tmp_path / "retrieval.jsonl",
        [
            {
                "id": 5,
                "question": "Câu hỏi E?",
                "selected_article_ids": [ARTICLE_A],
                "candidates": [
                    {"article_id": ARTICLE_A},
                    {"article_id": ARTICLE_B},
                    {"article_id": ARTICLE_B},
                    {"article_id": ARTICLE_C},
                    {"article_id": ARTICLE_D},
                ],
            }
        ],
    )
    output_path = tmp_path / "out.jsonl"
    summary_path = tmp_path / "summary.json"

    build_reranker_training_data(
        retrieval_path,
        legal_articles_path,
        output_path,
        summary_path,
        max_hard_negatives=2,
    )

    rows = _read_jsonl(output_path)
    assert rows[0]["hard_negative_article_ids"] == [ARTICLE_B, ARTICLE_C]
    assert ARTICLE_A not in rows[0]["hard_negative_article_ids"]


def test_summary_json_has_basic_counts(tmp_path: Path) -> None:
    legal_articles_path = _write_legal_articles(tmp_path)
    retrieval_path = _write_jsonl(
        tmp_path / "retrieval.jsonl",
        [
            {
                "id": 6,
                "question": "Câu hỏi F?",
                "selected_article_ids": [ARTICLE_A],
                "candidates": [{"article_id": ARTICLE_A}],
            },
            {
                "id": 7,
                "question": "Câu hỏi G?",
                "selected_article_ids": [ARTICLE_B],
                "candidates": [{"article_id": ARTICLE_C}, {"article_id": "BAD|Luật|Điều 1"}],
            },
        ],
    )
    output_path = tmp_path / "out.jsonl"
    summary_path = tmp_path / "summary.json"

    summary = build_reranker_training_data(retrieval_path, legal_articles_path, output_path, summary_path)
    summary_from_disk = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary == summary_from_disk
    assert summary["total_questions_seen"] == 2
    assert summary["samples_written"] == 1
    assert summary["questions_skipped_no_hard_negatives"] == 1
    assert summary["invalid_negative_article_ids_count"] == 1
    assert summary["weak_label"] is True
    assert summary["label_source"] == "retrieval_selected_articles"


def test_does_not_call_external_services(tmp_path: Path) -> None:
    legal_articles_path = _write_legal_articles(tmp_path)
    retrieval_path = _write_jsonl(
        tmp_path / "retrieval.jsonl",
        [
            {
                "id": 8,
                "question": "Câu hỏi H?",
                "selected_article_ids": [ARTICLE_A],
                "candidates": [{"article_id": ARTICLE_B}],
            }
        ],
    )
    output_path = tmp_path / "out.jsonl"
    summary_path = tmp_path / "summary.json"

    summary = build_reranker_training_data(retrieval_path, legal_articles_path, output_path, summary_path)

    assert summary["samples_written"] == 1
    assert "llm" not in json.dumps(summary).lower()
    assert "neo4j" not in json.dumps(summary).lower()


def _write_legal_articles(tmp_path: Path) -> Path:
    path = tmp_path / "legal_articles.parquet"
    pl.DataFrame(
        {
            "article_id": [ARTICLE_A, ARTICLE_B, ARTICLE_C, ARTICLE_D],
            "law_id": ["LAW-A", "LAW-B", "LAW-C", "LAW-D"],
            "law_title": ["Luật A", "Luật B", "Luật C", "Luật D"],
            "article_no": ["Điều 1", "Điều 2", "Điều 3", "Điều 4"],
            "article_text": ["A", "B", "C", "D"],
        }
    ).write_parquet(path)
    return path


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]
