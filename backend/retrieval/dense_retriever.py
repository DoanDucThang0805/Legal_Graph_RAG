"""Dense retrievers for Qdrant vector collections.

Module này chỉ chuẩn hóa kết quả dense retrieval. Citation chính thức vẫn phải
được sinh ở các bước sau từ canonical legal_articles registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.indexing.build_vector_index import (
    ANLE_UNITS_COLLECTION,
    LEGAL_ARTICLE_CHUNKS_COLLECTION,
    PHAPDIEN_ARTICLES_COLLECTION,
)
from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder
from backend.infrastructure.vector_store.qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

DEFAULT_RAW_TOP_K_MULTIPLIER = 5


@dataclass(frozen=True)
class DenseHit:
    """Normalized dense hit returned to upper retrieval layers."""

    source: str
    score: float
    article_id: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DenseRetriever:
    """Search dense Qdrant collections and return normalized hit objects."""

    def __init__(
        self,
        client: QdrantClient | Any | None = None,
        embedder: VNLegalLALEmbedder | Any | None = None,
        *,
        raw_top_k_multiplier: int = DEFAULT_RAW_TOP_K_MULTIPLIER,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self.raw_top_k_multiplier = max(raw_top_k_multiplier, 1)

    def search_legal_articles_dense(self, query: str, *, top_k: int = 10) -> list[DenseHit]:
        """Search legal chunk collection and dedup hits by canonical article_id."""

        normalized_query = _normalize_query(query)
        if not normalized_query or top_k <= 0:
            return []

        raw_top_k = max(top_k * self.raw_top_k_multiplier, top_k)
        raw_hits = self._search_collection(
            collection_name=LEGAL_ARTICLE_CHUNKS_COLLECTION,
            query=normalized_query,
            top_k=raw_top_k,
        )

        grouped_hits: dict[str, DenseHit] = {}
        for raw_hit in raw_hits:
            payload = _extract_payload(raw_hit)
            article_id = _clean_text(payload.get("article_id"))
            if article_id is None:
                logger.warning(
                    "Skip legal dense hit without canonical article_id: collection=%s id=%s",
                    LEGAL_ARTICLE_CHUNKS_COLLECTION,
                    getattr(raw_hit, "id", None),
                )
                continue

            candidate = DenseHit(
                source="legal_dense",
                score=_extract_score(raw_hit),
                article_id=article_id,
                text=_clean_text(payload.get("chunk_text")),
                metadata=_select_metadata(
                    payload,
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
                    extra={"collection": LEGAL_ARTICLE_CHUNKS_COLLECTION},
                ),
            )

            existing = grouped_hits.get(article_id)
            if existing is None or candidate.score > existing.score:
                grouped_hits[article_id] = candidate

        return sorted(grouped_hits.values(), key=lambda hit: hit.score, reverse=True)[:top_k]

    def search_phapdien_dense(self, query: str, *, top_k: int = 10) -> list[DenseHit]:
        """Search phapdien retrieval-only collection without assigning citations."""

        normalized_query = _normalize_query(query)
        if not normalized_query or top_k <= 0:
            return []

        raw_hits = self._search_collection(
            collection_name=PHAPDIEN_ARTICLES_COLLECTION,
            query=normalized_query,
            top_k=top_k,
        )
        return [
            DenseHit(
                source="phapdien_dense",
                score=_extract_score(raw_hit),
                article_id=None,
                text=_clean_text(_extract_payload(raw_hit).get("content_text")),
                metadata=_select_metadata(
                    _extract_payload(raw_hit),
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
                    extra={"collection": PHAPDIEN_ARTICLES_COLLECTION},
                ),
            )
            for raw_hit in raw_hits
        ]

    def search_anle_dense(self, query: str, *, top_k: int = 10) -> list[DenseHit]:
        """Search auxiliary anle collection without assigning official citations."""

        normalized_query = _normalize_query(query)
        if not normalized_query or top_k <= 0:
            return []

        raw_hits = self._search_collection(
            collection_name=ANLE_UNITS_COLLECTION,
            query=normalized_query,
            top_k=top_k,
        )
        return [
            DenseHit(
                source="anle_dense",
                score=_extract_score(raw_hit),
                article_id=None,
                text=_clean_text(_extract_payload(raw_hit).get("text")),
                metadata=_select_metadata(
                    _extract_payload(raw_hit),
                    ["unit_id", "case_id", "title", "source_url", "metadata_json"],
                    extra={"collection": ANLE_UNITS_COLLECTION},
                ),
            )
            for raw_hit in raw_hits
        ]

    def _search_collection(
        self,
        *,
        collection_name: str,
        query: str,
        top_k: int,
    ) -> list[Any]:
        query_vector = _to_float_list(self._embedding_model.encode_query(query))

        try:
            return _qdrant_vector_search(
                self._sdk_client,
                collection_name=collection_name,
                query_vector=query_vector,
                top_k=top_k,
            )
        except Exception:
            logger.exception("Dense search failed: collection=%s", collection_name)
            raise

    @property
    def _sdk_client(self) -> Any:
        if self._client is None:
            self._client = QdrantClient()
        return self._client.client if hasattr(self._client, "client") else self._client

    @property
    def _embedding_model(self) -> Any:
        if self._embedder is None:
            self._embedder = VNLegalLALEmbedder()
        return self._embedder


def _normalize_query(query: str) -> str:
    if query is None:
        return ""
    return str(query).strip()


def _to_float_list(vector: Any) -> list[float]:
    """Convert common vector containers to list[float] before Qdrant search."""

    if hasattr(vector, "detach"):
        vector = vector.detach()
    if hasattr(vector, "cpu"):
        vector = vector.cpu()
    if hasattr(vector, "numpy"):
        vector = vector.numpy()
    if hasattr(vector, "tolist"):
        vector = vector.tolist()

    if not isinstance(vector, list):
        vector = list(vector)

    # Một số model/fake có thể trả [[...]] cho một query; dense search cần vector 1-D.
    if vector and isinstance(vector[0], list):
        vector = vector[0]

    return [float(value) for value in vector]


def _qdrant_vector_search(
    sdk_client: Any,
    *,
    collection_name: str,
    query_vector: list[float],
    top_k: int,
) -> list[Any]:
    """Call Qdrant vector search across SDK versions.

    qdrant-client versions differ here: older clients expose ``search()``, while
    newer clients route vector search through ``query_points()`` and wrap results
    in a response object. Giữ phần tương thích này ở retriever để tầng trên không
    phụ thuộc vào chi tiết SDK.
    """

    if hasattr(sdk_client, "search"):
        return list(
            sdk_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
        )

    if hasattr(sdk_client, "query_points"):
        response = sdk_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        points = getattr(response, "points", response)
        return list(points)

    raise AttributeError("Qdrant client must expose search() or query_points()")


def _extract_payload(raw_hit: Any) -> dict[str, Any]:
    payload = getattr(raw_hit, "payload", None)
    if payload is None and isinstance(raw_hit, dict):
        payload = raw_hit.get("payload", {})
    if isinstance(payload, dict):
        return payload
    logger.warning("Invalid Qdrant hit payload: id=%s", getattr(raw_hit, "id", None))
    return {}


def _extract_score(raw_hit: Any) -> float:
    score = getattr(raw_hit, "score", None)
    if score is None and isinstance(raw_hit, dict):
        score = raw_hit.get("score")
    try:
        return float(score or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _select_metadata(
    payload: dict[str, Any],
    keys: list[str],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {key: value for key in keys if (value := payload.get(key)) not in (None, "")}
    if extra:
        metadata.update(extra)
    return metadata
