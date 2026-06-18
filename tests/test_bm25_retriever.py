from __future__ import annotations

from typing import Any

from backend.indexing.build_bm25_index import (
    ANLE_UNITS_INDEX,
    LEGAL_ARTICLE_CHUNKS_INDEX,
    PHAPDIEN_ARTICLES_INDEX,
)
from backend.retrieval.bm25_retriever import BM25Retriever


class FakeOpenSearchClient:
    def __init__(self, hits_by_index: dict[str, list[dict[str, Any]]]) -> None:
        self.hits_by_index = hits_by_index
        self.calls: list[dict[str, Any]] = []

    def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"index": index, "body": body})
        return {"hits": {"hits": self.hits_by_index.get(index, [])}}


def test_search_legal_articles_dedups_by_article_id_and_keeps_best_chunk() -> None:
    client = FakeOpenSearchClient(
        {
            LEGAL_ARTICLE_CHUNKS_INDEX: [
                {
                    "_score": 1.0,
                    "_source": {
                        "article_id": "law-a|Dieu 1",
                        "chunk_id": "chunk-low",
                        "chunk_text": "low score chunk",
                    },
                },
                {
                    "_score": 3.0,
                    "_source": {
                        "article_id": "law-a|Dieu 1",
                        "chunk_id": "chunk-best",
                        "chunk_text": "best score chunk",
                    },
                },
                {
                    "_score": 2.0,
                    "_source": {
                        "article_id": "law-b|Dieu 2",
                        "chunk_id": "chunk-b",
                        "chunk_text": "another article",
                    },
                },
            ]
        }
    )
    retriever = BM25Retriever(client=client)

    hits = retriever.search_legal_articles("doanh nghiệp nhỏ và vừa", top_k=2)

    assert [hit.article_id for hit in hits] == ["law-a|Dieu 1", "law-b|Dieu 2"]
    assert hits[0].score == 3.0
    assert hits[0].text == "best score chunk"
    assert hits[0].metadata["chunk_id"] == "chunk-best"
    assert hits[0].source == "legal_bm25"
    assert client.calls[0]["index"] == LEGAL_ARTICLE_CHUNKS_INDEX
    assert client.calls[0]["body"]["size"] == 10


def test_search_legal_articles_returns_top_k_after_dedup() -> None:
    client = FakeOpenSearchClient(
        {
            LEGAL_ARTICLE_CHUNKS_INDEX: [
                {"_score": 5, "_source": {"article_id": "a1", "chunk_id": "c1"}},
                {"_score": 4, "_source": {"article_id": "a1", "chunk_id": "c2"}},
                {"_score": 3, "_source": {"article_id": "a2", "chunk_id": "c3"}},
                {"_score": 2, "_source": {"article_id": "a3", "chunk_id": "c4"}},
            ]
        }
    )
    retriever = BM25Retriever(client=client)

    hits = retriever.search_legal_articles("thuế", top_k=2)

    assert [hit.article_id for hit in hits] == ["a1", "a2"]


def test_search_phapdien_does_not_assign_canonical_article_id() -> None:
    client = FakeOpenSearchClient(
        {
            PHAPDIEN_ARTICLES_INDEX: [
                {
                    "_score": 2.5,
                    "_source": {
                        "phapdien_id": "pd-1",
                        "article_title": "Điều 1",
                        "content_text": "Nội dung pháp điển",
                        "source_note_text": "Nguồn ghi chú",
                        "source_url": "https://example.test/pd-1",
                    },
                }
            ]
        }
    )
    retriever = BM25Retriever(client=client)

    hits = retriever.search_phapdien("hóa đơn", top_k=1)

    assert len(hits) == 1
    assert hits[0].source == "phapdien_bm25"
    assert hits[0].article_id is None
    assert hits[0].metadata["phapdien_id"] == "pd-1"
    assert hits[0].metadata["source_note_text"] == "Nguồn ghi chú"


def test_search_anle_does_not_assign_canonical_article_id() -> None:
    client = FakeOpenSearchClient(
        {
            ANLE_UNITS_INDEX: [
                {
                    "_score": 1.5,
                    "_source": {
                        "unit_id": "anle-1",
                        "case_id": "case-1",
                        "title": "Án lệ về hợp đồng",
                        "text": "Nội dung án lệ",
                        "metadata_json": '{"source": "toa-an"}',
                    },
                }
            ]
        }
    )
    retriever = BM25Retriever(client=client)

    hits = retriever.search_anle("hợp đồng", top_k=1)

    assert len(hits) == 1
    assert hits[0].source == "anle_bm25"
    assert hits[0].article_id is None
    assert hits[0].metadata["unit_id"] == "anle-1"
    assert hits[0].metadata["metadata_json"] == '{"source": "toa-an"}'


def test_empty_query_and_non_positive_top_k_return_empty_without_search() -> None:
    client = FakeOpenSearchClient({})
    retriever = BM25Retriever(client=client)

    assert retriever.search_legal_articles("   ", top_k=5) == []
    assert retriever.search_phapdien("query", top_k=0) == []
    assert retriever.search_anle("query", top_k=-1) == []
    assert client.calls == []
