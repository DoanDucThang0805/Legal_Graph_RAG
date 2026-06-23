from dataclasses import dataclass

from backend.retrieval.reranker import NoOpReranker, Reranker, get_default_reranker
from backend.schema.retrieval_result import RetrievalCandidate


@dataclass
class DummyHit:
    article_id: str
    score: float


def test_noop_reranker_returns_empty_list() -> None:
    assert NoOpReranker().rerank("q", []) == []


def test_noop_reranker_preserves_dict_candidate_order() -> None:
    candidates = [
        {"article_id": "article-a", "score": 0.9},
        {"article_id": "article-b", "score": 0.8},
        {"article_id": "article-c", "score": 0.7},
    ]

    reranked = NoOpReranker().rerank("question", candidates)

    assert reranked == candidates
    assert [candidate["article_id"] for candidate in reranked] == [
        "article-a",
        "article-b",
        "article-c",
    ]


def test_noop_reranker_returns_new_container_without_mutating_input() -> None:
    candidates = [DummyHit(article_id="article-a", score=1.0)]

    reranked = NoOpReranker().rerank("question", candidates)
    reranked.append(DummyHit(article_id="article-b", score=0.5))

    assert reranked is not candidates
    assert [candidate.article_id for candidate in candidates] == ["article-a"]


def test_noop_reranker_accepts_retrieval_candidate_objects() -> None:
    candidates = [
        RetrievalCandidate(article_id="article-a", source="exact", final_score=1.0),
        RetrievalCandidate(article_id="article-b", source="legal_bm25", final_score=0.5),
    ]

    reranked = NoOpReranker().rerank("question", candidates)

    assert [candidate.article_id for candidate in reranked] == ["article-a", "article-b"]
    assert reranked[0] is candidates[0]


def test_default_reranker_is_noop_protocol_compatible() -> None:
    reranker = get_default_reranker()

    assert isinstance(reranker, Reranker)
    assert reranker.rerank("q", [{"article_id": "article-a"}]) == [
        {"article_id": "article-a"}
    ]
