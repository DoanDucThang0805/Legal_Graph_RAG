"""Fusion utilities for canonical legal article candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from backend.schema.retrieval_result import RetrievalCandidate

DEFAULT_RRF_K = 60
EXACT_BOOST = 0.02
PHAPDIEN_MAPPED_BOOST = 0.005


@dataclass
class _FusionAccumulator:
    article_id: str
    source: str
    final_score: float = 0.0
    bm25_score: float = 0.0
    dense_score: float = 0.0
    exact_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


def reciprocal_rank_fusion(
    ranked_hit_lists: Iterable[Iterable[Any]],
    *,
    rrf_k: int = DEFAULT_RRF_K,
    apply_boost: bool = False,
) -> list[RetrievalCandidate]:
    """Fuse ranked hit lists by Reciprocal Rank Fusion.

    RRF uses rank only. Raw BM25/dense scores are kept in contribution metadata
    for debugging and later scoring layers.
    """

    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")

    accumulators: dict[str, _FusionAccumulator] = {}
    for hit_list in ranked_hit_lists:
        for rank, hit in enumerate(hit_list, start=1):
            article_id = _extract_canonical_article_id(hit)
            if article_id is None:
                continue

            source = _extract_source(hit)
            original_score = _extract_score(hit)
            contribution = 1.0 / (rrf_k + rank)
            accumulator = accumulators.get(article_id)
            if accumulator is None:
                accumulator = _FusionAccumulator(
                    article_id=article_id,
                    source=source,
                    metadata={"source_contributions": []},
                )
                accumulators[article_id] = accumulator

            accumulator.final_score += contribution
            _apply_source_score(accumulator, source, contribution)
            accumulator.metadata["source_contributions"].append(
                {
                    "source": source,
                    "rank": rank,
                    "original_score": original_score,
                    "rrf_contribution": contribution,
                }
            )

    candidates = [_to_retrieval_candidate(accumulator) for accumulator in accumulators.values()]
    if apply_boost:
        candidates = [score_boost(candidate) for candidate in candidates]
    return sorted(candidates, key=lambda candidate: candidate.final_score, reverse=True)


def merge_duplicate_articles(candidates: Iterable[Any]) -> list[RetrievalCandidate]:
    """Merge duplicate canonical article candidates without recalculating RRF."""

    accumulators: dict[str, _FusionAccumulator] = {}
    for candidate in candidates:
        article_id = _extract_canonical_article_id(candidate)
        if article_id is None:
            continue

        source = _extract_source(candidate)
        final_score = _extract_final_score(candidate)
        accumulator = accumulators.get(article_id)
        if accumulator is None:
            accumulator = _FusionAccumulator(
                article_id=article_id,
                source=source,
                final_score=final_score,
                bm25_score=_extract_named_score(candidate, "bm25_score"),
                dense_score=_extract_named_score(candidate, "dense_score"),
                exact_score=_extract_named_score(candidate, "exact_score"),
                metadata={"source_contributions": []},
            )
            accumulators[article_id] = accumulator
        else:
            accumulator.final_score += final_score
            accumulator.bm25_score += _extract_named_score(candidate, "bm25_score")
            accumulator.dense_score += _extract_named_score(candidate, "dense_score")
            accumulator.exact_score += _extract_named_score(candidate, "exact_score")

        accumulator.metadata["source_contributions"].extend(
            _extract_contributions(candidate, source)
        )

    return sorted(
        (_to_retrieval_candidate(accumulator) for accumulator in accumulators.values()),
        key=lambda candidate: candidate.final_score,
        reverse=True,
    )


def score_boost(candidate: RetrievalCandidate) -> RetrievalCandidate:
    """Apply small deterministic boosts after RRF.

    Boosts never change article_id and only apply to candidates that already
    have a valid canonical article_id.
    """

    boost = 0.0
    sources = {
        str(contribution.get("source", ""))
        for contribution in candidate.metadata.get("source_contributions", [])
        if isinstance(contribution, dict)
    }
    if "exact" in sources:
        boost += EXACT_BOOST
    if "phapdien_mapped" in sources:
        boost += PHAPDIEN_MAPPED_BOOST

    if boost <= 0:
        return candidate

    metadata = dict(candidate.metadata)
    metadata["score_boost"] = boost
    return candidate.model_copy(
        update={
            "final_score": candidate.final_score + boost,
            "metadata": metadata,
        }
    )


def _to_retrieval_candidate(accumulator: _FusionAccumulator) -> RetrievalCandidate:
    return RetrievalCandidate(
        article_id=accumulator.article_id,
        source=accumulator.source,
        bm25_score=accumulator.bm25_score,
        dense_score=accumulator.dense_score,
        exact_score=accumulator.exact_score,
        final_score=accumulator.final_score,
        metadata=accumulator.metadata,
    )


def _extract_canonical_article_id(hit: Any) -> str | None:
    article_id = _get_value(hit, "article_id")
    if not article_id:
        article_id = _get_value(hit, "legal_article_id")
    cleaned = str(article_id or "").strip()
    return cleaned or None


def _extract_source(hit: Any) -> str:
    source = str(_get_value(hit, "source") or "").strip()
    return source or "unknown"


def _extract_score(hit: Any) -> float:
    score = _get_value(hit, "score")
    if score is None:
        score = _get_value(hit, "final_score")
    return _to_float(score)


def _extract_final_score(candidate: Any) -> float:
    score = _get_value(candidate, "final_score")
    if score is None:
        score = _get_value(candidate, "score")
    return _to_float(score)


def _extract_named_score(candidate: Any, field_name: str) -> float:
    return _to_float(_get_value(candidate, field_name))


def _extract_contributions(candidate: Any, source: str) -> list[dict[str, Any]]:
    metadata = _get_value(candidate, "metadata") or {}
    if isinstance(metadata, dict):
        contributions = metadata.get("source_contributions")
        if isinstance(contributions, list):
            return [item for item in contributions if isinstance(item, dict)]

    return [
        {
            "source": source,
            "rank": None,
            "original_score": _extract_score(candidate),
            "rrf_contribution": _extract_final_score(candidate),
        }
    ]


def _apply_source_score(accumulator: _FusionAccumulator, source: str, contribution: float) -> None:
    if "bm25" in source:
        accumulator.bm25_score += contribution
    elif "dense" in source:
        accumulator.dense_score += contribution
    elif source == "exact":
        accumulator.exact_score += contribution


def _get_value(obj: Any, field_name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(field_name)
    return getattr(obj, field_name, None)


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
