from pathlib import Path

import polars as pl

from backend.indexing import build_bm25_index as bm25


def test_build_all_bm25_indexes_uses_chunk_and_filtered_phapdien_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: dict[str, Path] = {}

    def fake_legal(path: str | Path, **kwargs) -> None:
        calls["legal"] = Path(path)

    def fake_phapdien(path: str | Path, **kwargs) -> None:
        calls["phapdien"] = Path(path)

    def fake_anle(path: str | Path, **kwargs) -> None:
        calls["anle"] = Path(path)

    monkeypatch.setattr(bm25, "build_legal_article_chunks_bm25_index", fake_legal)
    monkeypatch.setattr(bm25, "build_phapdien_articles_bm25_index", fake_phapdien)
    monkeypatch.setattr(bm25, "build_anle_units_bm25_index", fake_anle)

    bm25.build_all_bm25_indexes(client=object(), processed_dir=tmp_path)

    assert calls["legal"] == tmp_path / "legal_article_chunks.parquet"
    assert calls["phapdien"] == tmp_path / "phapdien_articles_index.parquet"
    assert calls["anle"] == tmp_path / "anle_units.parquet"


def test_legal_chunk_bm25_payload_keeps_parent_article_and_chunk_ids() -> None:
    df = pl.DataFrame(
        [
            {
                "chunk_id": "article-1|chunk:0",
                "article_id": "article-1",
                "law_id": "L1",
                "law_title": "Luat Test",
                "article_no": "Dieu 1",
                "article_title": "Quy dinh chung",
                "chunk_index": 0,
                "chunk_text": "Noi dung chunk",
                "source_url": "https://example.test",
                "domain": "test",
                "status": "active",
            }
        ]
    )

    actions = list(
        bm25._iter_bulk_actions(
            df,
            index_name=bm25.LEGAL_ARTICLE_CHUNKS_INDEX,
            id_column="chunk_id",
        )
    )
    source = actions[0][0]["_source"]

    assert actions[0][0]["_index"] == "legal_article_chunks_bm25"
    assert source["chunk_id"] == "article-1|chunk:0"
    assert source["article_id"] == "article-1"
    assert source["chunk_text"] == "Noi dung chunk"


def test_legal_chunk_bm25_mapping_indexes_chunk_text() -> None:
    properties = bm25._legal_article_chunks_mapping()["mappings"]["properties"]

    assert "chunk_text" in properties
    assert properties["chunk_text"]["type"] == "text"
    assert "article_text" not in properties
    assert properties["chunk_id"]["type"] == "keyword"
    assert properties["article_id"]["type"] == "keyword"
