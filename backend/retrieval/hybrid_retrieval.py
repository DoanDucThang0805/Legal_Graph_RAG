"""Hybrid retrieval orchestration for canonical legal article candidates."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from backend.retrieval.article_selector import ArticleSelector
from backend.retrieval.bm25_retriever import BM25Retriever
from backend.retrieval.dense_retriever import DenseRetriever
from backend.retrieval.exact_retriever import ExactRetriever
from backend.retrieval.fusion import reciprocal_rank_fusion
from backend.retrieval.phapdien_retriever import PhapdienMappedRetriever
from backend.schema.retrieval_result import RetrievalCandidate

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 10


@dataclass(slots=True)
class HybridRetrievalResult:
    question: str
    candidates: list[RetrievalCandidate]
    selected_article_ids: list[str]
    selected_candidates: list[RetrievalCandidate]
    debug: dict[str, Any] = field(default_factory=dict)


class HybridLegalRetriever:
    """Coordinate baseline legal retrieval components without generating answers."""

    def __init__(
        self,
        *,
        bm25_retriever: BM25Retriever | Any | None = None,
        dense_retriever: DenseRetriever | Any | None = None,
        exact_retriever: ExactRetriever | Any | None = None,
        phapdien_retriever: PhapdienMappedRetriever | Any | None = None,
        article_selector: ArticleSelector | Any | None = None,
    ) -> None:
        self._bm25_retriever = bm25_retriever
        self._dense_retriever = dense_retriever
        self._exact_retriever = exact_retriever
        self._phapdien_retriever = phapdien_retriever
        self._article_selector = article_selector or ArticleSelector()

    def retrieve(
        self,
        question: str | Mapping[str, Any] | Any,
        *,
        answer_type: str | None = None,
        complexity: str | None = None,
        top_k: int = DEFAULT_TOP_K,
        bm25_top_k: int | None = None,
        dense_top_k: int | None = None,
        exact_top_k: int | None = None,
        phapdien_top_k: int | None = None,
        max_articles: int | None = None,
        min_score: float | None = None,
    ) -> HybridRetrievalResult:
        """Run the Phase 4 baseline retrieval pipeline.

        The orchestrator only coordinates retrieval, fusion, and selection. It
        does not generate answers or derive submission citations.
        """

        payload = _extract_query_payload(question)
        normalized_question = payload.question
        resolved_answer_type = answer_type if answer_type is not None else payload.answer_type
        resolved_complexity = complexity if complexity is not None else payload.complexity

        debug: dict[str, Any] = {
            "query": normalized_question,
            "answer_type": resolved_answer_type,
            "complexity": resolved_complexity,
            "top_k": top_k,
            "stage_counts": {},
            "errors": {},
        }

        if not normalized_question or top_k <= 0:
            debug["reason"] = "empty_query_or_non_positive_top_k"
            return HybridRetrievalResult(
                question=normalized_question,
                candidates=[],
                selected_article_ids=[],
                selected_candidates=[],
                debug=debug,
            )

        resolved_bm25_top_k = _resolve_top_k(bm25_top_k, top_k)
        resolved_dense_top_k = _resolve_top_k(dense_top_k, top_k)
        resolved_exact_top_k = _resolve_top_k(exact_top_k, top_k)
        resolved_phapdien_top_k = _resolve_top_k(phapdien_top_k, top_k)
        debug["top_k_by_stage"] = {
            "bm25_legal": resolved_bm25_top_k,
            "dense_legal": resolved_dense_top_k,
            "exact": resolved_exact_top_k,
            "phapdien_mapped": resolved_phapdien_top_k,
        }

        bm25_hits = self._run_stage(
            "bm25_legal",
            lambda: self._get_bm25_retriever().search_legal_articles(
                normalized_question,
                top_k=resolved_bm25_top_k,
            ),
            debug,
        )
        dense_hits = self._run_stage(
            "dense_legal",
            lambda: self._get_dense_retriever().search_legal_articles_dense(
                normalized_question,
                top_k=resolved_dense_top_k,
            ),
            debug,
        )
        exact_hits = self._run_stage(
            "exact",
            lambda: self._get_exact_retriever().search(
                normalized_question,
                top_k=resolved_exact_top_k,
            ),
            debug,
        )
        phapdien_hits = self._run_stage(
            "phapdien_mapped",
            lambda: self._get_phapdien_retriever().search_and_map(
                normalized_question,
                top_k=resolved_phapdien_top_k,
            ),
            debug,
        )

        fused_candidates = reciprocal_rank_fusion(
            [bm25_hits, dense_hits, exact_hits, phapdien_hits]
        )
        debug["stage_counts"]["fused_candidates"] = len(fused_candidates)

        selected_candidates = self._article_selector.select(
            fused_candidates,
            answer_type=resolved_answer_type,
            complexity=resolved_complexity,
            max_articles=max_articles,
            min_score=min_score,
        )
        selected_article_ids = [candidate.article_id for candidate in selected_candidates]
        debug["stage_counts"]["selected_candidates"] = len(selected_candidates)
        debug["selected_article_ids_count"] = len(selected_article_ids)

        return HybridRetrievalResult(
            question=normalized_question,
            candidates=fused_candidates,
            selected_article_ids=selected_article_ids,
            selected_candidates=selected_candidates,
            debug=debug,
        )

    def _run_stage(
        self,
        stage_name: str,
        search_fn: Callable[[], list[Any]],
        debug: dict[str, Any],
    ) -> list[Any]:
        try:
            hits = search_fn()
        except Exception as exc:
            logger.exception("Hybrid retrieval stage failed: %s", stage_name)
            debug["errors"][stage_name] = str(exc)
            debug["stage_counts"][stage_name] = 0
            return []

        debug["stage_counts"][stage_name] = len(hits)
        return hits

    def _get_bm25_retriever(self) -> BM25Retriever | Any:
        if self._bm25_retriever is None:
            self._bm25_retriever = BM25Retriever()
        return self._bm25_retriever

    def _get_dense_retriever(self) -> DenseRetriever | Any:
        if self._dense_retriever is None:
            self._dense_retriever = DenseRetriever()
        return self._dense_retriever

    def _get_exact_retriever(self) -> ExactRetriever | Any:
        if self._exact_retriever is None:
            self._exact_retriever = ExactRetriever()
        return self._exact_retriever

    def _get_phapdien_retriever(self) -> PhapdienMappedRetriever | Any:
        if self._phapdien_retriever is None:
            self._phapdien_retriever = PhapdienMappedRetriever()
        return self._phapdien_retriever


@dataclass(slots=True)
class _QueryPayload:
    question: str
    answer_type: str | None = None
    complexity: str | None = None


def _extract_query_payload(value: str | Mapping[str, Any] | Any) -> _QueryPayload:
    if isinstance(value, str):
        return _QueryPayload(question=value.strip())

    question = _extract_field(value, "question")
    answer_type = _extract_field(value, "answer_type")
    complexity = _extract_field(value, "complexity")
    return _QueryPayload(
        question=str(question or "").strip(),
        answer_type=_clean_optional_text(answer_type),
        complexity=_clean_optional_text(complexity),
    )


def _extract_field(value: Mapping[str, Any] | Any, field_name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(field_name)
    return getattr(value, field_name, None)


def _clean_optional_text(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _resolve_top_k(stage_top_k: int | None, default_top_k: int) -> int:
    return default_top_k if stage_top_k is None else stage_top_k
