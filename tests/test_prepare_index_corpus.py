import polars as pl

from backend.knowledge_processing.prepare_index_corpus import (
    build_legal_article_chunks,
    build_phapdien_index_corpus,
    split_text_into_chunks,
)


def test_split_text_into_chunks_keeps_short_text_single_chunk() -> None:
    assert split_text_into_chunks("Nội dung ngắn", chunk_size=100, chunk_overlap=10) == ["Nội dung ngắn"]


def test_split_text_into_chunks_uses_overlap() -> None:
    chunks = split_text_into_chunks("abcdefghij", chunk_size=4, chunk_overlap=1)
    assert chunks == ["abcd", "defg", "ghij"]


def test_build_legal_article_chunks_preserves_parent_article_id() -> None:
    legal_articles_df = pl.DataFrame(
        [
            {
                "article_id": "L1|Luật Test|Điều 1",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 1",
                "article_text": "a" * 10,
                "source_url": "https://example.test",
                "domain": "test",
                "status": "active",
            }
        ]
    )

    chunks_df = build_legal_article_chunks(legal_articles_df, chunk_size=4, chunk_overlap=1)

    assert chunks_df.height == 3
    assert chunks_df["article_id"].to_list() == ["L1|Luật Test|Điều 1"] * 3
    assert chunks_df["chunk_id"].n_unique() == 3
    assert chunks_df["chunk_text"].to_list() == ["aaaa", "aaaa", "aaaa"]


def test_build_phapdien_index_corpus_filters_empty_content() -> None:
    phapdien_df = pl.DataFrame(
        [
            {"phapdien_id": "p1", "content_text": "Có nội dung"},
            {"phapdien_id": "p2", "content_text": ""},
        ]
    )

    result = build_phapdien_index_corpus(phapdien_df)

    assert result.height == 1
    assert result["phapdien_id"][0] == "p1"
