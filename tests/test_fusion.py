from dataclasses import dataclass

import pytest

from backend.retrieval.fusion import (
    EXACT_BOOST,
    PHAPDIEN_MAPPED_BOOST,
    merge_duplicate_articles,
    reciprocal_rank_fusion,
    score_boost,
)
from backend.schema.retrieval_result import RetrievalCandidate


@dataclass
class DummyHit:
    article_id: str | None
    source: str
    score: float
    metadata: dict | None = None


@dataclass
class DummyMappedHit:
    legal_article_id: str
    source: str
    score: float


def test_reciprocal_rank_fusion_uses_rank_based_formula() -> None:
    hits = [
        DummyHit(article_id="article-a", source="legal_bm25", score=100.0),
        DummyHit(article_id="article-b", source="legal_bm25", score=999.0),
    ]

    candidates = reciprocal_rank_fusion([hits], rrf_k=60)

    assert [candidate.article_id for candidate in candidates] == ["article-a", "article-b"]
    assert candidates[0].final_score == pytest.approx(1 / (60 + 1))
    assert candidates[1].final_score == pytest.approx(1 / (60 + 2))
    assert candidates[0].final_score > candidates[1].final_score


def test_reciprocal_rank_fusion_merges_duplicate_article_ids() -> None:
    bm25_hits = [DummyHit(article_id="article-a", source="legal_bm25", score=10.0)]
    dense_hits = [DummyHit(article_id="article-a", source="legal_dense", score=0.7)]

    candidates = reciprocal_rank_fusion([bm25_hits, dense_hits], rrf_k=60)

    assert len(candidates) == 1
    candidate = candidates[0]
    expected = (1 / (60 + 1)) + (1 / (60 + 1))
    assert candidate.article_id == "article-a"
    assert candidate.final_score == pytest.approx(expected)
    assert candidate.bm25_score == pytest.approx(1 / (60 + 1))
    assert candidate.dense_score == pytest.approx(1 / (60 + 1))
    assert len(candidate.metadata["source_contributions"]) == 2


def test_reciprocal_rank_fusion_keeps_source_contribution_metadata() -> None:
    hits = [DummyHit(article_id="article-a", source="exact", score=1.0)]

    candidate = reciprocal_rank_fusion([hits], rrf_k=60)[0]
    contribution = candidate.metadata["source_contributions"][0]

    assert contribution["source"] == "exact"
    assert contribution["rank"] == 1
    assert contribution["original_score"] == pytest.approx(1.0)
    assert contribution["rrf_contribution"] == pytest.approx(1 / (60 + 1))


def test_reciprocal_rank_fusion_uses_legal_article_id_alias() -> None:
    hits = [DummyMappedHit(legal_article_id="canonical-article", source="phapdien_mapped", score=95.0)]

    candidates = reciprocal_rank_fusion([hits], rrf_k=60)

    assert len(candidates) == 1
    assert candidates[0].article_id == "canonical-article"
    assert candidates[0].metadata["source_contributions"][0]["source"] == "phapdien_mapped"


def test_reciprocal_rank_fusion_skips_hits_without_canonical_article_id() -> None:
    hits = [
        {"chunk_id": "chunk-1", "source": "legal_bm25", "score": 1.0},
        {"phapdien_id": "phapdien:1", "source": "phapdien_bm25", "score": 1.0},
        {"unit_id": "anle:1", "source": "anle_dense", "score": 1.0},
        {"article_id": "canonical-article", "source": "exact", "score": 1.0},
    ]

    candidates = reciprocal_rank_fusion([hits], rrf_k=60)

    assert [candidate.article_id for candidate in candidates] == ["canonical-article"]
    assert all(candidate.article_id not in {"chunk-1", "phapdien:1", "anle:1"} for candidate in candidates)


def test_score_boost_is_separate_and_deterministic() -> None:
    candidate = reciprocal_rank_fusion(
        [
            [DummyHit(article_id="article-a", source="exact", score=1.0)],
            [DummyHit(article_id="article-a", source="phapdien_mapped", score=95.0)],
        ],
        rrf_k=60,
    )[0]

    boosted = score_boost(candidate)

    assert boosted.article_id == candidate.article_id
    assert boosted.final_score == pytest.approx(
        candidate.final_score + EXACT_BOOST + PHAPDIEN_MAPPED_BOOST
    )
    assert "score_boost" in boosted.metadata
    assert "score_boost" not in candidate.metadata


def test_merge_duplicate_articles_preserves_contributions() -> None:
    candidate_a = RetrievalCandidate(
        article_id="article-a",
        source="legal_bm25",
        final_score=0.1,
        bm25_score=0.1,
        metadata={
            "source_contributions": [
                {
                    "source": "legal_bm25",
                    "rank": 1,
                    "original_score": 10.0,
                    "rrf_contribution": 0.1,
                }
            ]
        },
    )
    candidate_b = RetrievalCandidate(
        article_id="article-a",
        source="legal_dense",
        final_score=0.2,
        dense_score=0.2,
        metadata={
            "source_contributions": [
                {
                    "source": "legal_dense",
                    "rank": 1,
                    "original_score": 0.8,
                    "rrf_contribution": 0.2,
                }
            ]
        },
    )

    merged = merge_duplicate_articles([candidate_a, candidate_b])

    assert len(merged) == 1
    assert merged[0].article_id == "article-a"
    assert merged[0].final_score == pytest.approx(0.3)
    assert merged[0].bm25_score == pytest.approx(0.1)
    assert merged[0].dense_score == pytest.approx(0.2)
    assert len(merged[0].metadata["source_contributions"]) == 2
