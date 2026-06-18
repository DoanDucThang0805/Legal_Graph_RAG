"""BM25 retrievers for OpenSearch indexes.

Module này chỉ chuẩn hóa kết quả retrieval. Citation chính thức vẫn phải được
sinh ở các bước sau từ canonical legal_articles registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.indexing.build_bm25_index import (
    ANLE_UNITS_INDEX,
    LEGAL_ARTICLE_CHUNKS_INDEX,
    PHAPDIEN_ARTICLES_INDEX,
)
from backend.infrastructure.search_engine.opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)

DEFAULT_RAW_TOP_K_MULTIPLIER = 5


@dataclass(frozen=True)
class BM25Hit:
    """Normalized BM25 hit returned to upper retrieval layers."""

    source: str
    score: float
    article_id: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BM25Retriever:
    """Search BM25 OpenSearch indexes and return normalized hit objects."""

    def __init__(
        self,
        client: OpenSearchClient | Any | None = None,
        *,
        raw_top_k_multiplier: int = DEFAULT_RAW_TOP_K_MULTIPLIER,
    ) -> None:
        self._client = client
        self.raw_top_k_multiplier = max(raw_top_k_multiplier, 1)

    def search_legal_articles(self, query: str, *, top_k: int = 10) -> list[BM25Hit]:
        """Search legal article chunk index and dedup hits by canonical article_id."""

        normalized_query = _normalize_query(query)
        if not normalized_query or top_k <= 0:
            return []

        raw_top_k = max(top_k * self.raw_top_k_multiplier, top_k)
        raw_hits = self._search_index(
            index_name=LEGAL_ARTICLE_CHUNKS_INDEX,
            query=normalized_query,
            top_k=raw_top_k,
            fields=["chunk_text^3", "article_title^2", "law_title", "law_id", "article_no"],
        )

        grouped_hits: dict[str, BM25Hit] = {}
        for raw_hit in raw_hits:
            source = _extract_source(raw_hit)
            article_id = _clean_text(source.get("article_id"))
            if article_id is None:
                logger.warning(
                    "Skip legal BM25 hit without canonical article_id: index=%s id=%s",
                    LEGAL_ARTICLE_CHUNKS_INDEX,
                    raw_hit.get("_id"),
                )
                continue

            score = _extract_score(raw_hit)
            candidate = BM25Hit(
                source="legal_bm25",
                score=score,
                article_id=article_id,
                text=_clean_text(source.get("chunk_text")),
                metadata=_select_metadata(
                    source,
                    [
                        "chunk_id",
                        "law_id",
                        "law_title",
                        "article_no",
                        "article_title",
                        "chunk_index",
                        "source_url",
                        "domain",
                        "status",
                    ],
                    extra={"index": LEGAL_ARTICLE_CHUNKS_INDEX},
                ),
            )

            existing = grouped_hits.get(article_id)
            if existing is None or candidate.score > existing.score:
                grouped_hits[article_id] = candidate

        return sorted(grouped_hits.values(), key=lambda hit: hit.score, reverse=True)[:top_k]

    def search_phapdien(self, query: str, *, top_k: int = 10) -> list[BM25Hit]:
        """Search phapdien retrieval-only index without assigning canonical citations."""

        normalized_query = _normalize_query(query)
        if not normalized_query or top_k <= 0:
            return []

        raw_hits = self._search_index(
            index_name=PHAPDIEN_ARTICLES_INDEX,
            query=normalized_query,
            top_k=top_k,
            fields=[
                "content_text^3",
                "article_title^2",
                "source_note_text^2",
                "related_note_text",
                "topic_title",
                "subject_title",
                "chapter_title",
            ],
        )
        return [
            BM25Hit(
                source="phapdien_bm25",
                score=_extract_score(raw_hit),
                article_id=None,
                text=_clean_text(_extract_source(raw_hit).get("content_text")),
                metadata=_select_metadata(
                    _extract_source(raw_hit),
                    [
                        "phapdien_id",
                        "article_title",
                        "source_note_text",
                        "source_url",
                        "topic_title",
                        "subject_title",
                        "chapter_title",
                        "related_note_text",
                        "source_links_json",
                    ],
                    extra={"index": PHAPDIEN_ARTICLES_INDEX},
                ),
            )
            for raw_hit in raw_hits
        ]

    def search_anle(self, query: str, *, top_k: int = 10) -> list[BM25Hit]:
        """Search auxiliary anle index without assigning canonical citations."""

        normalized_query = _normalize_query(query)
        if not normalized_query or top_k <= 0:
            return []

        raw_hits = self._search_index(
            index_name=ANLE_UNITS_INDEX,
            query=normalized_query,
            top_k=top_k,
            fields=["text^3", "title^2", "case_id", "metadata_json"],
        )
        return [
            BM25Hit(
                source="anle_bm25",
                score=_extract_score(raw_hit),
                article_id=None,
                text=_clean_text(_extract_source(raw_hit).get("text")),
                metadata=_select_metadata(
                    _extract_source(raw_hit),
                    ["unit_id", "case_id", "title", "source_url", "metadata_json"],
                    extra={"index": ANLE_UNITS_INDEX},
                ),
            )
            for raw_hit in raw_hits
        ]

    def _search_index(
        self,
        *,
        index_name: str,
        query: str,
        top_k: int,
        fields: list[str],
    ) -> list[dict[str, Any]]:
        body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": fields,
                    "type": "best_fields",
                }
            },
        }

        try:
            response = self._sdk_client.search(index=index_name, body=body)
        except Exception:
            logger.exception("BM25 search failed: index=%s", index_name)
            raise

        hits = response.get("hits", {}).get("hits", [])
        if not isinstance(hits, list):
            logger.warning("Invalid OpenSearch hits payload: index=%s", index_name)
            return []
        return [hit for hit in hits if isinstance(hit, dict)]

    @property
    def _sdk_client(self) -> Any:
        if self._client is None:
            self._client = OpenSearchClient()
        return self._client.client if hasattr(self._client, "client") else self._client


def _normalize_query(query: str) -> str:
    if query is None:
        return ""
    return str(query).strip()


def _extract_source(raw_hit: dict[str, Any]) -> dict[str, Any]:
    source = raw_hit.get("_source", {})
    if isinstance(source, dict):
        return source
    logger.warning("Invalid OpenSearch hit _source payload: id=%s", raw_hit.get("_id"))
    return {}


def _extract_score(raw_hit: dict[str, Any]) -> float:
    try:
        return float(raw_hit.get("_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _select_metadata(
    source: dict[str, Any],
    keys: list[str],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {key: value for key in keys if (value := source.get(key)) not in (None, "")}
    if extra:
        metadata.update(extra)
    return metadata
