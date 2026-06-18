from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.indexing.build_vector_index import (
    ANLE_UNITS_COLLECTION,
    LEGAL_ARTICLE_CHUNKS_COLLECTION,
    PHAPDIEN_ARTICLES_COLLECTION,
)
from backend.retrieval.dense_retriever import DenseRetriever


@dataclass(frozen=True)
class FakeQdrantHit:
    score: float
    payload: dict[str, Any]
    id: str = "point-id"


class FakeQdrantClient:
    def __init__(self, hits_by_collection: dict[str, list[FakeQdrantHit]]) -> None:
        self.hits_by_collection = hits_by_collection
        self.calls: list[dict[str, Any]] = []

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        with_payload: bool,
        with_vectors: bool,
    ) -> list[FakeQdrantHit]:
        self.calls.append(
            {
                "collection_name": collection_name,
                "query_vector": query_vector,
                "limit": limit,
                "with_payload": with_payload,
                "with_vectors": with_vectors,
            }
        )
        return self.hits_by_collection.get(collection_name, [])


@dataclass(frozen=True)
class FakeQueryPointsResponse:
    points: list[FakeQdrantHit]


class FakeQdrantQueryPointsClient:
    def __init__(self, hits_by_collection: dict[str, list[FakeQdrantHit]]) -> None:
        self.hits_by_collection = hits_by_collection
        self.calls: list[dict[str, Any]] = []

    def query_points(
        self,
        *,
        collection_name: str,
        query: list[float],
        limit: int,
        with_payload: bool,
        with_vectors: bool,
    ) -> FakeQueryPointsResponse:
        self.calls.append(
            {
                "collection_name": collection_name,
                "query": query,
                "limit": limit,
                "with_payload": with_payload,
                "with_vectors": with_vectors,
            }
        )
        return FakeQueryPointsResponse(points=self.hits_by_collection.get(collection_name, []))


class FakeEmbedder:
    def __init__(self, vector: Any | None = None) -> None:
        self.vector = vector if vector is not None else [0.1, 0.2, 0.3]
        self.encode_query_calls: list[str] = []
        self.encode_documents_calls: list[str] = []

    def encode_query(self, query: str) -> Any:
        self.encode_query_calls.append(query)
        return self.vector

    def encode_documents(self, documents: list[str]) -> list[list[float]]:
        self.encode_documents_calls.extend(documents)
        return [[0.0]]


def test_search_legal_articles_dense_dedups_by_article_id_and_keeps_best_chunk() -> None:
    client = FakeQdrantClient(
        {
            LEGAL_ARTICLE_CHUNKS_COLLECTION: [
                FakeQdrantHit(
                    score=0.1,
                    payload={
                        "article_id": "law-a|Dieu 1",
                        "chunk_id": "chunk-low",
                        "chunk_text": "low score chunk",
                    },
                ),
                FakeQdrantHit(
                    score=0.9,
                    payload={
                        "article_id": "law-a|Dieu 1",
                        "chunk_id": "chunk-best",
                        "chunk_text": "best score chunk",
                    },
                ),
                FakeQdrantHit(
                    score=0.7,
                    payload={
                        "article_id": "law-b|Dieu 2",
                        "chunk_id": "chunk-b",
                        "chunk_text": "another article",
                    },
                ),
            ]
        }
    )
    embedder = FakeEmbedder()
    retriever = DenseRetriever(client=client, embedder=embedder)

    hits = retriever.search_legal_articles_dense("doanh nghiệp nhỏ và vừa", top_k=2)

    assert [hit.article_id for hit in hits] == ["law-a|Dieu 1", "law-b|Dieu 2"]
    assert hits[0].source == "legal_dense"
    assert hits[0].score == 0.9
    assert hits[0].text == "best score chunk"
    assert hits[0].metadata["chunk_id"] == "chunk-best"
    assert hits[0].metadata["collection"] == LEGAL_ARTICLE_CHUNKS_COLLECTION
    assert client.calls[0]["collection_name"] == LEGAL_ARTICLE_CHUNKS_COLLECTION
    assert client.calls[0]["limit"] == 10
    assert client.calls[0]["query_vector"] == [0.1, 0.2, 0.3]


def test_search_legal_articles_dense_uses_encode_query_not_document_encoder() -> None:
    client = FakeQdrantClient({LEGAL_ARTICLE_CHUNKS_COLLECTION: []})
    embedder = FakeEmbedder(vector=[[1, 2, 3]])
    retriever = DenseRetriever(client=client, embedder=embedder)

    retriever.search_legal_articles_dense("thuế", top_k=1)

    assert embedder.encode_query_calls == ["thuế"]
    assert embedder.encode_documents_calls == []
    assert client.calls[0]["query_vector"] == [1.0, 2.0, 3.0]


def test_search_legal_articles_dense_supports_qdrant_query_points_client() -> None:
    client = FakeQdrantQueryPointsClient(
        {
            LEGAL_ARTICLE_CHUNKS_COLLECTION: [
                FakeQdrantHit(
                    score=0.5,
                    payload={
                        "article_id": "law-a|Dieu 1",
                        "chunk_id": "chunk-a",
                        "chunk_text": "content",
                    },
                )
            ]
        }
    )
    retriever = DenseRetriever(client=client, embedder=FakeEmbedder())

    hits = retriever.search_legal_articles_dense("thuế", top_k=1)

    assert len(hits) == 1
    assert hits[0].article_id == "law-a|Dieu 1"
    assert client.calls[0]["collection_name"] == LEGAL_ARTICLE_CHUNKS_COLLECTION
    assert client.calls[0]["query"] == [0.1, 0.2, 0.3]
    assert client.calls[0]["limit"] == 5


def test_search_phapdien_dense_does_not_assign_canonical_article_id() -> None:
    client = FakeQdrantClient(
        {
            PHAPDIEN_ARTICLES_COLLECTION: [
                FakeQdrantHit(
                    score=0.8,
                    payload={
                        "phapdien_id": "pd-1",
                        "article_title": "Điều 1",
                        "content_text": "Nội dung pháp điển",
                        "source_note_text": "Nguồn ghi chú",
                        "source_url": "https://example.test/pd-1",
                    },
                )
            ]
        }
    )
    retriever = DenseRetriever(client=client, embedder=FakeEmbedder())

    hits = retriever.search_phapdien_dense("hóa đơn", top_k=1)

    assert len(hits) == 1
    assert hits[0].source == "phapdien_dense"
    assert hits[0].article_id is None
    assert hits[0].metadata["phapdien_id"] == "pd-1"
    assert hits[0].metadata["source_note_text"] == "Nguồn ghi chú"


def test_search_anle_dense_does_not_assign_canonical_article_id() -> None:
    client = FakeQdrantClient(
        {
            ANLE_UNITS_COLLECTION: [
                FakeQdrantHit(
                    score=0.6,
                    payload={
                        "unit_id": "anle-1",
                        "case_id": "case-1",
                        "title": "Án lệ về hợp đồng",
                        "text": "Nội dung án lệ",
                        "metadata_json": '{"source": "toa-an"}',
                    },
                )
            ]
        }
    )
    retriever = DenseRetriever(client=client, embedder=FakeEmbedder())

    hits = retriever.search_anle_dense("hợp đồng", top_k=1)

    assert len(hits) == 1
    assert hits[0].source == "anle_dense"
    assert hits[0].article_id is None
    assert hits[0].metadata["unit_id"] == "anle-1"
    assert hits[0].metadata["metadata_json"] == '{"source": "toa-an"}'


def test_empty_query_and_non_positive_top_k_return_empty_without_embedding_or_search() -> None:
    client = FakeQdrantClient({})
    embedder = FakeEmbedder()
    retriever = DenseRetriever(client=client, embedder=embedder)

    assert retriever.search_legal_articles_dense("   ", top_k=5) == []
    assert retriever.search_phapdien_dense("query", top_k=0) == []
    assert retriever.search_anle_dense("query", top_k=-1) == []
    assert client.calls == []
    assert embedder.encode_query_calls == []
