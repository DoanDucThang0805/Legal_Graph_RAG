"""Phapdien retrieval mapper to canonical legal articles.

Phapdien chỉ là nguồn retrieval. Module này map phapdien hits sang
canonical legal_article_id bằng phapdien_to_vbpl_map; không dùng article_title
của phapdien làm citation chính thức.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import polars as pl

from backend.config.settings import get_settings
from backend.retrieval.bm25_retriever import BM25Retriever
from backend.retrieval.dense_retriever import DenseRetriever

logger = logging.getLogger(__name__)

DEFAULT_RAW_TOP_K_MULTIPLIER = 5


@dataclass(frozen=True)
class MappedPhapdienHit:
    """Canonical candidate mapped from a phapdien retrieval hit."""

    legal_article_id: str
    score: float
    mapping_score: float
    retrieval_score: float
    retrieval_source: str
    source: str = "phapdien_mapped"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def article_id(self) -> str:
        """Alias for downstream retrieval/fusion components."""

        return self.legal_article_id


class PhapdienSearchHit(Protocol):
    source: str
    score: float
    article_id: str | None
    text: str | None
    metadata: dict[str, Any]


class PhapdienRetrieverProtocol(Protocol):
    def search_phapdien(self, query: str, *, top_k: int = 10) -> list[PhapdienSearchHit]: ...


class PhapdienDenseRetrieverProtocol(Protocol):
    def search_phapdien_dense(self, query: str, *, top_k: int = 10) -> list[PhapdienSearchHit]: ...


class PhapdienMappedRetriever:
    """Search phapdien BM25/dense hits and map them to canonical articles."""

    def __init__(
        self,
        mapping_path: str | Path | None = None,
        *,
        bm25_retriever: PhapdienRetrieverProtocol | None = None,
        dense_retriever: PhapdienDenseRetrieverProtocol | None = None,
        raw_top_k_multiplier: int = DEFAULT_RAW_TOP_K_MULTIPLIER,
    ) -> None:
        self.mapping_path = _resolve_mapping_path(mapping_path)
        self.mapping = _load_mapping(self.mapping_path)
        self.bm25_retriever = bm25_retriever
        self.dense_retriever = dense_retriever
        self.raw_top_k_multiplier = max(raw_top_k_multiplier, 1)

    def search_and_map(self, query: str, top_k: int = 5) -> list[MappedPhapdienHit]:
        """Return mapped canonical candidates only.

        Unmapped phapdien hits are logged and skipped; they are never promoted
        to citations because relevant_articles must come from legal_articles.
        """

        normalized_query = _normalize_query(query)
        if not normalized_query or top_k <= 0:
            return []

        raw_top_k = max(top_k * self.raw_top_k_multiplier, top_k)
        raw_hits = self._search_phapdien_hits(normalized_query, raw_top_k)
        ranked_hits = _attach_rank(raw_hits)

        mapped_by_article: dict[str, MappedPhapdienHit] = {}
        for hit, rank in ranked_hits:
            phapdien_id = _extract_phapdien_id(hit)
            if phapdien_id is None:
                logger.warning("Skip phapdien hit without phapdien_id: source=%s", hit.source)
                continue

            mapping_record = self.mapping.get(phapdien_id)
            if mapping_record is None:
                logger.info("Skip unmapped phapdien hit: phapdien_id=%s source=%s", phapdien_id, hit.source)
                continue

            candidate = _build_mapped_hit(hit, rank, phapdien_id, mapping_record)
            existing = mapped_by_article.get(candidate.legal_article_id)
            if existing is None or _is_better_candidate(candidate, existing):
                mapped_by_article[candidate.legal_article_id] = candidate

        return sorted(
            mapped_by_article.values(),
            key=lambda item: (-item.mapping_score, item.metadata.get("best_rank", 10**9), -item.retrieval_score),
        )[:top_k]

    def _search_phapdien_hits(self, query: str, top_k: int) -> list[PhapdienSearchHit]:
        hits: list[PhapdienSearchHit] = []

        try:
            hits.extend(self._bm25.search_phapdien(query, top_k=top_k))
        except Exception:
            logger.exception("Phapdien BM25 search failed")
            raise

        try:
            hits.extend(self._dense.search_phapdien_dense(query, top_k=top_k))
        except Exception:
            logger.exception("Phapdien dense search failed")
            raise

        return hits

    @property
    def _bm25(self) -> PhapdienRetrieverProtocol:
        if self.bm25_retriever is None:
            self.bm25_retriever = BM25Retriever()
        return self.bm25_retriever

    @property
    def _dense(self) -> PhapdienDenseRetrieverProtocol:
        if self.dense_retriever is None:
            self.dense_retriever = DenseRetriever()
        return self.dense_retriever


def _resolve_mapping_path(mapping_path: str | Path | None) -> Path:
    if mapping_path is not None:
        return Path(mapping_path)
    return get_settings().paths.processed_dir / "phapdien_to_vbpl_map.parquet"


def _load_mapping(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Phapdien mapping parquet not found: {path}")

    df = pl.read_parquet(path)
    required_columns = {
        "phapdien_id",
        "legal_article_id",
        "law_id",
        "law_title",
        "article_no",
        "mapping_score",
        "mapping_method",
    }
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing phapdien mapping columns: {missing_columns}")

    mapping: dict[str, dict[str, Any]] = {}
    for row in df.iter_rows(named=True):
        phapdien_id = _clean_text(row.get("phapdien_id"))
        legal_article_id = _clean_text(row.get("legal_article_id"))
        if phapdien_id is None or legal_article_id is None:
            logger.warning("Skip invalid phapdien mapping row: phapdien_id=%s", phapdien_id)
            continue
        mapping[phapdien_id] = {
            "legal_article_id": legal_article_id,
            "law_id": _clean_text(row.get("law_id")),
            "law_title": _clean_text(row.get("law_title")),
            "article_no": _clean_text(row.get("article_no")),
            "mapping_score": _to_float(row.get("mapping_score")),
            "mapping_method": _clean_text(row.get("mapping_method")),
        }
    return mapping


def _attach_rank(hits: list[PhapdienSearchHit]) -> list[tuple[PhapdienSearchHit, int]]:
    return [(hit, rank) for rank, hit in enumerate(hits, start=1)]


def _extract_phapdien_id(hit: PhapdienSearchHit) -> str | None:
    return _clean_text(hit.metadata.get("phapdien_id"))


def _build_mapped_hit(
    hit: PhapdienSearchHit,
    rank: int,
    phapdien_id: str,
    mapping_record: dict[str, Any],
) -> MappedPhapdienHit:
    mapping_score = _to_float(mapping_record.get("mapping_score"))
    retrieval_score = _to_float(hit.score)
    # Score riêng cho nguồn phapdien-mapped giữ mapping quality làm trọng tâm.
    # BM25/dense score chỉ lưu metadata, không cộng trực tiếp để tránh trộn thang điểm.
    score = mapping_score

    return MappedPhapdienHit(
        legal_article_id=str(mapping_record["legal_article_id"]),
        score=score,
        mapping_score=mapping_score,
        retrieval_score=retrieval_score,
        retrieval_source=hit.source,
        metadata={
            "phapdien_id": phapdien_id,
            "mapping_method": mapping_record.get("mapping_method"),
            "law_id": mapping_record.get("law_id"),
            "law_title": mapping_record.get("law_title"),
            "article_no": mapping_record.get("article_no"),
            "retrieval_source": hit.source,
            "retrieval_score": retrieval_score,
            "best_rank": rank,
            "phapdien_metadata": dict(hit.metadata),
        },
    )


def _is_better_candidate(candidate: MappedPhapdienHit, existing: MappedPhapdienHit) -> bool:
    candidate_rank = int(candidate.metadata.get("best_rank", 10**9))
    existing_rank = int(existing.metadata.get("best_rank", 10**9))
    return (
        candidate.mapping_score,
        -candidate_rank,
        candidate.retrieval_score,
    ) > (
        existing.mapping_score,
        -existing_rank,
        existing.retrieval_score,
    )


def _normalize_query(query: str) -> str:
    if query is None:
        return ""
    return str(query).strip()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
