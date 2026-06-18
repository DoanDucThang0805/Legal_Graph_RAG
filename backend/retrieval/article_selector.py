"""Select canonical legal article candidates after fusion."""

from __future__ import annotations

from typing import Any

from backend.schema.retrieval_result import RetrievalCandidate

DEFAULT_MAX_ARTICLES = 7
MULTI_HOP_MAX_ARTICLES = 12

ANSWER_TYPE_MAX_ARTICLES: dict[str, int] = {
    "deadline": 4,
    "accounting_account": 4,
    "yes_no": 5,
    "procedure": 7,
    "dossier": 7,
    "sanction": 6,
    "conditions": 8,
    "obligations": 8,
}


class ArticleSelector:
    """Thin wrapper around select_articles for dependency injection."""

    def select(
        self,
        candidates: list[RetrievalCandidate],
        *,
        answer_type: str | None = None,
        complexity: str | None = None,
        max_articles: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievalCandidate]:
        return select_articles(
            candidates,
            answer_type=answer_type,
            complexity=complexity,
            max_articles=max_articles,
            min_score=min_score,
        )


def select_articles(
    candidates: list[RetrievalCandidate],
    *,
    answer_type: str | None = None,
    complexity: str | None = None,
    max_articles: int | None = None,
    min_score: float | None = None,
) -> list[RetrievalCandidate]:
    """Deduplicate, rank, threshold, and limit fused article candidates."""

    limit = _resolve_max_articles(
        answer_type=answer_type,
        complexity=complexity,
        max_articles=max_articles,
    )
    if limit <= 0:
        return []

    deduped: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        article_id = _extract_article_id(candidate)
        if article_id is None:
            continue

        score = _candidate_score(candidate)
        if min_score is not None and score < min_score:
            continue

        current = deduped.get(article_id)
        if current is None or score > _candidate_score(current):
            deduped[article_id] = candidate

    ranked = sorted(
        deduped.values(),
        key=lambda candidate: (_candidate_score(candidate), candidate.article_id),
        reverse=True,
    )
    return ranked[:limit]


def _resolve_max_articles(
    *,
    answer_type: str | None,
    complexity: str | None,
    max_articles: int | None,
) -> int:
    if max_articles is not None:
        return max_articles

    normalized_complexity = _normalize_label(complexity)
    if normalized_complexity == "multi_hop":
        return MULTI_HOP_MAX_ARTICLES

    normalized_answer_type = _normalize_label(answer_type)
    return ANSWER_TYPE_MAX_ARTICLES.get(normalized_answer_type, DEFAULT_MAX_ARTICLES)


def _extract_article_id(candidate: Any) -> str | None:
    article_id = _get_value(candidate, "article_id")
    cleaned = str(article_id or "").strip()
    return cleaned or None


def _candidate_score(candidate: Any) -> float:
    final_score = _to_float(_get_value(candidate, "final_score"))
    if final_score != 0.0:
        return final_score

    component_scores = [
        _to_float(_get_value(candidate, "rerank_score")),
        _to_float(_get_value(candidate, "graph_score")),
        _to_float(_get_value(candidate, "exact_score")),
        _to_float(_get_value(candidate, "dense_score")),
        _to_float(_get_value(candidate, "bm25_score")),
    ]
    return max(component_scores, default=0.0)


def _normalize_label(value: str | None) -> str:
    return str(value or "").strip().lower()


def _get_value(obj: Any, field_name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(field_name)
    return getattr(obj, field_name, None)


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
