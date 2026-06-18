from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from backend.retrieval.phapdien_retriever import PhapdienMappedRetriever


@dataclass(frozen=True)
class FakeRetrievalHit:
    source: str
    score: float
    article_id: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FakeBM25Retriever:
    def __init__(self, hits: list[FakeRetrievalHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search_phapdien(self, query: str, *, top_k: int = 10) -> list[FakeRetrievalHit]:
        self.calls.append((query, top_k))
        return self.hits[:top_k]


class FakeDenseRetriever:
    def __init__(self, hits: list[FakeRetrievalHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search_phapdien_dense(self, query: str, *, top_k: int = 10) -> list[FakeRetrievalHit]:
        self.calls.append((query, top_k))
        return self.hits[:top_k]


def _write_mapping(path: Path) -> None:
    df = pl.DataFrame(
        [
            {
                "phapdien_id": "pd-1",
                "legal_article_id": "law-a|title-a|Điều 1",
                "law_id": "law-a",
                "law_title": "title-a",
                "article_no": "Điều 1",
                "mapping_score": 95.0,
                "mapping_method": "item_id_article_no",
            },
            {
                "phapdien_id": "pd-2",
                "legal_article_id": "law-b|title-b|Điều 2",
                "law_id": "law-b",
                "law_title": "title-b",
                "article_no": "Điều 2",
                "mapping_score": 88.0,
                "mapping_method": "law_id_article_no",
            },
            {
                "phapdien_id": "pd-3",
                "legal_article_id": "law-a|title-a|Điều 1",
                "law_id": "law-a",
                "law_title": "title-a",
                "article_no": "Điều 1",
                "mapping_score": 90.0,
                "mapping_method": "item_id_fuzzy_text",
            },
        ]
    )
    df.write_parquet(path)


def test_search_and_map_returns_mapped_canonical_candidates_only(tmp_path: Path) -> None:
    mapping_path = tmp_path / "phapdien_to_vbpl_map.parquet"
    _write_mapping(mapping_path)
    bm25 = FakeBM25Retriever(
        [
            FakeRetrievalHit("phapdien_bm25", 12.0, metadata={"phapdien_id": "pd-1"}),
            FakeRetrievalHit("phapdien_bm25", 30.0, metadata={"phapdien_id": "pd-unmapped"}),
        ]
    )
    dense = FakeDenseRetriever([])
    retriever = PhapdienMappedRetriever(
        mapping_path,
        bm25_retriever=bm25,
        dense_retriever=dense,
    )

    hits = retriever.search_and_map("hỗ trợ doanh nghiệp nhỏ và vừa", top_k=5)

    assert len(hits) == 1
    assert hits[0].legal_article_id == "law-a|title-a|Điều 1"
    assert hits[0].article_id == hits[0].legal_article_id
    assert hits[0].source == "phapdien_mapped"
    assert hits[0].mapping_score == 95.0
    assert hits[0].metadata["phapdien_id"] == "pd-1"
    assert hits[0].metadata["phapdien_metadata"]["phapdien_id"] == "pd-1"


def test_search_and_map_dedups_by_legal_article_id_using_mapping_score_then_rank(tmp_path: Path) -> None:
    mapping_path = tmp_path / "phapdien_to_vbpl_map.parquet"
    _write_mapping(mapping_path)
    bm25 = FakeBM25Retriever(
        [
            FakeRetrievalHit("phapdien_bm25", 100.0, metadata={"phapdien_id": "pd-3"}),
            FakeRetrievalHit("phapdien_bm25", 1.0, metadata={"phapdien_id": "pd-1"}),
        ]
    )
    dense = FakeDenseRetriever([])
    retriever = PhapdienMappedRetriever(
        mapping_path,
        bm25_retriever=bm25,
        dense_retriever=dense,
    )

    hits = retriever.search_and_map("query", top_k=5)

    assert len(hits) == 1
    assert hits[0].legal_article_id == "law-a|title-a|Điều 1"
    assert hits[0].mapping_score == 95.0
    assert hits[0].retrieval_score == 1.0
    assert hits[0].metadata["phapdien_id"] == "pd-1"


def test_search_and_map_uses_rank_when_mapping_score_ties(tmp_path: Path) -> None:
    mapping_path = tmp_path / "phapdien_to_vbpl_map.parquet"
    pl.DataFrame(
        [
            {
                "phapdien_id": "pd-1",
                "legal_article_id": "law-a|title-a|Điều 1",
                "law_id": "law-a",
                "law_title": "title-a",
                "article_no": "Điều 1",
                "mapping_score": 95.0,
                "mapping_method": "method-a",
            },
            {
                "phapdien_id": "pd-2",
                "legal_article_id": "law-a|title-a|Điều 1",
                "law_id": "law-a",
                "law_title": "title-a",
                "article_no": "Điều 1",
                "mapping_score": 95.0,
                "mapping_method": "method-b",
            },
        ]
    ).write_parquet(mapping_path)
    bm25 = FakeBM25Retriever(
        [
            FakeRetrievalHit("phapdien_bm25", 1.0, metadata={"phapdien_id": "pd-1"}),
            FakeRetrievalHit("phapdien_bm25", 100.0, metadata={"phapdien_id": "pd-2"}),
        ]
    )
    retriever = PhapdienMappedRetriever(
        mapping_path,
        bm25_retriever=bm25,
        dense_retriever=FakeDenseRetriever([]),
    )

    hits = retriever.search_and_map("query", top_k=5)

    assert len(hits) == 1
    assert hits[0].metadata["phapdien_id"] == "pd-1"
    assert hits[0].metadata["best_rank"] == 1


def test_empty_query_and_non_positive_top_k_return_empty_without_search(tmp_path: Path) -> None:
    mapping_path = tmp_path / "phapdien_to_vbpl_map.parquet"
    _write_mapping(mapping_path)
    bm25 = FakeBM25Retriever([FakeRetrievalHit("phapdien_bm25", 1.0, metadata={"phapdien_id": "pd-1"})])
    dense = FakeDenseRetriever([])
    retriever = PhapdienMappedRetriever(
        mapping_path,
        bm25_retriever=bm25,
        dense_retriever=dense,
    )

    assert retriever.search_and_map("   ", top_k=5) == []
    assert retriever.search_and_map("query", top_k=0) == []
    assert bm25.calls == []
    assert dense.calls == []
