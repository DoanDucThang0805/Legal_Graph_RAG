from pathlib import Path

import polars as pl

from backend.qa.article_context_loader import ArticleContextLoader, load_selected_article_contexts


def test_load_selected_article_contexts_falls_back_to_default_chunk_path(tmp_path: Path) -> None:
    legal_articles_path = tmp_path / "legal_articles.parquet"
    legal_chunks_path = tmp_path / "legal_article_chunks.parquet"
    article_a = "L1|Luật Test|Điều 1"
    article_b = "L1|Luật Test|Điều 2"

    _write_legal_articles(
        legal_articles_path,
        [
            _article_row(article_a, "Điều 1", "Text từ legal_articles"),
            _article_row(article_b, "Điều 2", ""),
        ],
    )
    pl.DataFrame(
        [
            {"article_id": article_b, "chunk_index": 1, "chunk_text": "Chunk B2"},
            {"article_id": article_b, "chunk_index": 0, "chunk_text": "Chunk B1"},
            {"article_id": article_b, "chunk_index": 2, "chunk_text": ""},
            {"article_id": article_b, "chunk_index": 3, "chunk_text": "Chunk B2"},
        ]
    ).write_parquet(legal_chunks_path)

    articles = load_selected_article_contexts(
        [article_a, article_b],
        legal_articles_path=legal_articles_path,
    )

    assert [article["article_id"] for article in articles] == [article_a, article_b]
    assert articles[0]["article_text"] == "Text từ legal_articles"
    assert articles[1]["article_text"] == "Chunk B1\n\nChunk B2"
    assert articles[1]["law_id"] == "L1"
    assert articles[1]["law_title"] == "Luật Test"
    assert articles[1]["article_no"] == "Điều 2"
    assert articles[1]["article_title"] == "Tiêu đề Điều 2"


def test_article_context_loader_does_not_crash_when_chunks_file_missing(tmp_path: Path) -> None:
    legal_articles_path = tmp_path / "legal_articles.parquet"
    article_id = "L1|Luật Test|Điều 1"
    _write_legal_articles(legal_articles_path, [_article_row(article_id, "Điều 1", "")])

    loader = ArticleContextLoader(
        legal_articles_path=legal_articles_path,
        legal_article_chunks_path=tmp_path / "missing_chunks.parquet",
    )

    articles = loader.load_articles([article_id])

    assert len(articles) == 1
    assert articles[0]["article_id"] == article_id
    assert articles[0]["article_text"] == ""


def test_chunk_fallback_goes_through_existing_truncation(tmp_path: Path) -> None:
    legal_articles_path = tmp_path / "legal_articles.parquet"
    legal_chunks_path = tmp_path / "legal_article_chunks.parquet"
    article_id = "L1|Luật Test|Điều 1"
    _write_legal_articles(legal_articles_path, [_article_row(article_id, "Điều 1", "")])
    pl.DataFrame(
        [{"article_id": article_id, "chunk_index": 0, "chunk_text": "a" * 100}]
    ).write_parquet(legal_chunks_path)

    articles = load_selected_article_contexts(
        [article_id],
        legal_articles_path=legal_articles_path,
        max_article_chars=40,
    )

    assert len(articles[0]["article_text"]) == 40


def test_total_context_budget_keeps_all_text_articles_non_empty(tmp_path: Path) -> None:
    legal_articles_path = tmp_path / "legal_articles.parquet"
    article_ids = [f"L1|Luật Test|Điều {index}" for index in range(1, 8)]
    _write_legal_articles(
        legal_articles_path,
        [_article_row(article_id, f"Điều {index}", f"text-{index} " * 300) for index, article_id in enumerate(article_ids, start=1)],
    )

    articles = load_selected_article_contexts(
        article_ids,
        legal_articles_path=legal_articles_path,
        max_article_chars=700,
        max_total_context_chars=3500,
    )
    lengths = [len(article["article_text"]) for article in articles]

    assert [article["article_id"] for article in articles] == article_ids
    assert all(length > 0 for length in lengths)
    assert sum(lengths) <= 3500
    assert lengths[0] >= lengths[-1]


def test_tiny_total_context_budget_is_shared_when_possible(tmp_path: Path) -> None:
    legal_articles_path = tmp_path / "legal_articles.parquet"
    article_ids = [f"L1|Luật Test|Điều {index}" for index in range(1, 4)]
    _write_legal_articles(
        legal_articles_path,
        [_article_row(article_id, f"Điều {index}", "abcdef") for index, article_id in enumerate(article_ids, start=1)],
    )

    articles = load_selected_article_contexts(
        article_ids,
        legal_articles_path=legal_articles_path,
        max_total_context_chars=3,
    )
    lengths = [len(article["article_text"]) for article in articles]

    assert lengths == [1, 1, 1]
    assert sum(lengths) == 3


def test_truly_empty_article_text_can_remain_empty(tmp_path: Path) -> None:
    legal_articles_path = tmp_path / "legal_articles.parquet"
    article_a = "L1|Luật Test|Điều 1"
    article_b = "L1|Luật Test|Điều 2"
    _write_legal_articles(
        legal_articles_path,
        [
            _article_row(article_a, "Điều 1", "Có nội dung"),
            _article_row(article_b, "Điều 2", ""),
        ],
    )

    articles = load_selected_article_contexts(
        [article_a, article_b],
        legal_articles_path=legal_articles_path,
        max_total_context_chars=20,
    )

    assert len(articles[0]["article_text"]) > 0
    assert articles[1]["article_text"] == ""


def test_legacy_wrapper_uses_fair_total_context_allocation(tmp_path: Path) -> None:
    legal_articles_path = tmp_path / "legal_articles.parquet"
    article_ids = ["L1|Luật Test|Điều 1", "L1|Luật Test|Điều 2"]
    _write_legal_articles(
        legal_articles_path,
        [
            _article_row(article_ids[0], "Điều 1", "a" * 100),
            _article_row(article_ids[1], "Điều 2", "b" * 100),
        ],
    )

    articles = load_selected_article_contexts(
        article_ids,
        legal_articles_path=legal_articles_path,
        max_total_context_chars=2,
    )

    assert [len(article["article_text"]) for article in articles] == [1, 1]


def _write_legal_articles(path: Path, rows: list[dict[str, str]]) -> None:
    pl.DataFrame(rows).write_parquet(path)


def _article_row(article_id: str, article_no: str, article_text: str) -> dict[str, str]:
    return {
        "article_id": article_id,
        "law_id": "L1",
        "law_title": "Luật Test",
        "article_no": article_no,
        "article_title": f"Tiêu đề {article_no}",
        "article_text": article_text,
    }
