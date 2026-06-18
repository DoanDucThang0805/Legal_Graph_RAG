from typing import cast

from backend.retrieval.article_selector import ArticleSelector, select_articles
from backend.schema.retrieval_result import RetrievalCandidate


def candidate(
    article_id: str,
    final_score: float,
    *,
    metadata: dict | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        article_id=article_id,
        source="fusion",
        final_score=final_score,
        metadata=metadata or {},
    )


def test_select_articles_deduplicates_and_keeps_highest_score() -> None:
    candidates = [
        candidate("article-a", 0.1),
        candidate("article-b", 0.5),
        candidate("article-a", 0.8),
    ]

    selected = select_articles(candidates)

    assert [item.article_id for item in selected] == ["article-a", "article-b"]
    assert selected[0].final_score == 0.8


def test_select_articles_sorts_by_score_descending() -> None:
    candidates = [
        candidate("article-a", 0.1),
        candidate("article-b", 0.7),
        candidate("article-c", 0.4),
    ]

    selected = select_articles(candidates)

    assert [item.article_id for item in selected] == ["article-b", "article-c", "article-a"]


def test_select_articles_respects_answer_type_limits() -> None:
    candidates = [candidate(f"article-{idx}", 100 - idx) for idx in range(10)]

    assert len(select_articles(candidates, answer_type="deadline")) == 4
    assert len(select_articles(candidates, answer_type="accounting_account")) == 4
    assert len(select_articles(candidates, answer_type="yes_no")) == 5
    assert len(select_articles(candidates, answer_type="procedure")) == 7
    assert len(select_articles(candidates, answer_type="dossier")) == 7
    assert len(select_articles(candidates, answer_type="sanction")) == 6
    assert len(select_articles(candidates, answer_type="conditions")) == 8
    assert len(select_articles(candidates, answer_type="obligations")) == 8


def test_select_articles_uses_multi_hop_limit_before_answer_type() -> None:
    candidates = [candidate(f"article-{idx}", 100 - idx) for idx in range(20)]

    selected = select_articles(candidates, answer_type="deadline", complexity="multi_hop")

    assert len(selected) == 12


def test_select_articles_allows_max_articles_override() -> None:
    candidates = [candidate(f"article-{idx}", 100 - idx) for idx in range(20)]

    selected = select_articles(
        candidates,
        answer_type="deadline",
        complexity="multi_hop",
        max_articles=3,
    )

    assert len(selected) == 3


def test_select_articles_applies_threshold_when_provided() -> None:
    candidates = [
        candidate("article-a", 0.2),
        candidate("article-b", 0.6),
        candidate("article-c", 0.8),
    ]

    selected = select_articles(candidates, min_score=0.5)

    assert [item.article_id for item in selected] == ["article-c", "article-b"]


def test_select_articles_default_threshold_does_not_drop_zero_score_candidate() -> None:
    candidates = [candidate("article-a", 0.0)]

    selected = select_articles(candidates)

    assert [item.article_id for item in selected] == ["article-a"]


def test_select_articles_skips_candidate_without_canonical_article_id() -> None:
    malformed = RetrievalCandidate.model_construct(
        article_id="",
        source="fusion",
        final_score=10.0,
        metadata={
            "chunk_id": "chunk-1",
            "phapdien_id": "phapdien:1",
            "unit_id": "anle:1",
        },
    )
    candidates = cast(
        list[RetrievalCandidate],
        [
            malformed,
            candidate(
                "canonical-article",
                1.0,
                metadata={
                    "chunk_id": "chunk-2",
                    "phapdien_id": "phapdien:2",
                    "unit_id": "anle:2",
                },
            ),
        ],
    )

    selected = select_articles(candidates)

    assert [item.article_id for item in selected] == ["canonical-article"]
    non_canonical_ids = {
        "chunk-1",
        "phapdien:1",
        "anle:1",
        "chunk-2",
        "phapdien:2",
        "anle:2",
    }
    assert all(
        item.article_id not in non_canonical_ids
        for item in selected
    )


def test_select_articles_uses_component_score_when_final_score_is_zero() -> None:
    bm25_candidate = RetrievalCandidate(
        article_id="article-a",
        source="fusion",
        bm25_score=0.4,
    )
    exact_candidate = RetrievalCandidate(
        article_id="article-b",
        source="fusion",
        exact_score=0.9,
    )

    selected = select_articles([bm25_candidate, exact_candidate], min_score=0.5)

    assert [item.article_id for item in selected] == ["article-b"]


def test_article_selector_wrapper_delegates_to_function() -> None:
    selector = ArticleSelector()
    candidates = [candidate("article-a", 0.1), candidate("article-b", 0.9)]

    selected = selector.select(candidates, max_articles=1)

    assert [item.article_id for item in selected] == ["article-b"]
