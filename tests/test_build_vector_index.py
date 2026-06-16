from pathlib import Path

from backend.indexing import build_vector_index as vector


def test_build_all_vector_indexes_uses_chunk_and_filtered_phapdien_sources(
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

    monkeypatch.setattr(vector, "build_legal_article_chunks_vector_index", fake_legal)
    monkeypatch.setattr(vector, "build_phapdien_articles_vector_index", fake_phapdien)
    monkeypatch.setattr(vector, "build_anle_units_vector_index", fake_anle)

    vector.build_all_vector_indexes(client=object(), embedder=object(), processed_dir=tmp_path)

    assert calls["legal"] == tmp_path / "legal_article_chunks.parquet"
    assert calls["phapdien"] == tmp_path / "phapdien_articles_index.parquet"
    assert calls["anle"] == tmp_path / "anle_units.parquet"


def test_legal_vector_text_uses_chunk_text_with_legal_context() -> None:
    row = {
        "chunk_id": "article-1|chunk:0",
        "article_id": "article-1",
        "law_title": "Luat Test",
        "article_no": "Dieu 1",
        "article_title": "Quy dinh chung",
        "chunk_text": "Noi dung chunk can embed",
    }

    text = vector._build_legal_chunk_text(row)

    assert "Tên văn bản: Luat Test" in text
    assert "Điều: Dieu 1" in text
    assert "Tiêu đề điều: Quy dinh chung" in text
    assert "Nội dung chunk:\nNoi dung chunk can embed" in text


def test_legal_vector_payload_contains_parent_and_chunk_metadata() -> None:
    row = {
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

    payload = vector._clean_payload(row)

    for key in [
        "chunk_id",
        "article_id",
        "law_id",
        "law_title",
        "article_no",
        "article_title",
        "chunk_index",
        "source_url",
        "domain",
        "status",
    ]:
        assert key in payload
    assert payload["chunk_text"]
    assert vector.LEGAL_ARTICLE_CHUNKS_COLLECTION == "legal_article_chunks_dense"
