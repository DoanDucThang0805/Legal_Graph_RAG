"""Load canonical legal article context for answer generation.

This helper hydrates article IDs selected by retrieval into article dictionaries
for prompt construction. It is not a retriever and does not rank or select
articles.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_ARTICLE_COLUMNS = [
    "article_id",
    "law_id",
    "law_title",
    "article_no",
    "article_title",
    "article_text",
]
TRUNCATED_SUFFIX = "... [Nội dung điều luật đã được rút gọn để phù hợp giới hạn context]"


def load_selected_article_contexts(
    article_ids: list[str],
    legal_articles_path: str | Path,
    max_article_chars: int | None = None,
    max_total_context_chars: int | None = None,
    legal_article_chunks_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Hydrate canonical article IDs from legal_articles.parquet.

    Args:
        article_ids: Canonical article IDs in retrieval-selected order.
        legal_articles_path: Path to the canonical legal_articles parquet file.
        max_article_chars: Optional per-article article_text character limit.
        max_total_context_chars: Optional total article_text character budget.
        legal_article_chunks_path: Optional path to legal_article_chunks parquet
            for fallback text when canonical article_text is empty.

    Returns:
        Article dictionaries preserving the input order after deduplication.
    """

    unique_article_ids = _deduplicate_article_ids(article_ids)
    if not unique_article_ids:
        return []

    articles_path = Path(legal_articles_path)
    if not articles_path.is_file():
        raise FileNotFoundError(f"legal_articles parquet does not exist: {articles_path}")

    try:
        import polars as pl
    except ImportError as exc:
        raise RuntimeError("Missing dependency: polars") from exc

    df = pl.read_parquet(articles_path)
    missing_columns = [column for column in REQUIRED_ARTICLE_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"legal_articles parquet missing required columns: {missing_columns}")

    matched_df = df.filter(pl.col("article_id").is_in(unique_article_ids)).select(REQUIRED_ARTICLE_COLUMNS)
    articles_by_id = {str(row["article_id"]): row for row in matched_df.to_dicts()}

    missing_ids = [article_id for article_id in unique_article_ids if article_id not in articles_by_id]
    if missing_ids:
        logger.warning("Missing %d selected article IDs in legal_articles parquet", len(missing_ids))

    ordered_articles = [articles_by_id[article_id] for article_id in unique_article_ids if article_id in articles_by_id]
    ordered_articles = _fill_empty_article_texts_from_chunks(
        ordered_articles,
        legal_articles_path=articles_path,
        legal_article_chunks_path=legal_article_chunks_path,
        pl=pl,
    )
    return _truncate_article_texts(
        ordered_articles,
        max_article_chars=max_article_chars,
        max_total_context_chars=max_total_context_chars,
    )


class ArticleContextLoader:
    """Small wrapper for hydrating selected article IDs into QA context."""

    def __init__(
        self,
        legal_articles_path: str | Path,
        legal_article_chunks_path: str | Path | None = None,
        max_article_chars: int | None = None,
        max_total_context_chars: int | None = None,
    ) -> None:
        self.legal_articles_path = Path(legal_articles_path)
        self.legal_article_chunks_path = (
            Path(legal_article_chunks_path) if legal_article_chunks_path is not None else None
        )
        self.max_article_chars = max_article_chars
        self.max_total_context_chars = max_total_context_chars

    def load_articles(self, article_ids: list[str]) -> list[dict[str, Any]]:
        """Load selected articles using the same behavior as the module function."""
        return load_selected_article_contexts(
            article_ids=article_ids,
            legal_articles_path=self.legal_articles_path,
            max_article_chars=self.max_article_chars,
            max_total_context_chars=self.max_total_context_chars,
            legal_article_chunks_path=self.legal_article_chunks_path,
        )


def _deduplicate_article_ids(article_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_article_ids: list[str] = []

    for article_id in article_ids:
        normalized_id = str(article_id or "").strip()
        if not normalized_id or normalized_id in seen:
            continue
        seen.add(normalized_id)
        unique_article_ids.append(normalized_id)

    return unique_article_ids


def _fill_empty_article_texts_from_chunks(
    articles: list[dict[str, Any]],
    legal_articles_path: Path,
    legal_article_chunks_path: str | Path | None,
    pl: Any,
) -> list[dict[str, Any]]:
    fallback_ids = [
        str(article.get("article_id"))
        for article in articles
        if article.get("article_id") and not _has_text(article.get("article_text"))
    ]
    if not fallback_ids:
        return articles

    chunks_path = _resolve_chunks_path(legal_articles_path, legal_article_chunks_path)
    chunk_texts_by_article_id = _load_chunk_texts_by_article_id(
        chunks_path=chunks_path,
        article_ids=fallback_ids,
        pl=pl,
    )
    if not chunk_texts_by_article_id:
        return articles

    hydrated_articles: list[dict[str, Any]] = []
    filled_count = 0
    for article in articles:
        article_copy = dict(article)
        article_id = str(article_copy.get("article_id") or "")
        fallback_text = chunk_texts_by_article_id.get(article_id)
        if fallback_text and not _has_text(article_copy.get("article_text")):
            article_copy["article_text"] = fallback_text
            filled_count += 1
        hydrated_articles.append(article_copy)

    if filled_count:
        logger.info("Filled empty article_text from chunks for %d selected articles", filled_count)
    return hydrated_articles


def _resolve_chunks_path(
    legal_articles_path: Path,
    legal_article_chunks_path: str | Path | None,
) -> Path:
    if legal_article_chunks_path is not None:
        return Path(legal_article_chunks_path)
    return legal_articles_path.with_name("legal_article_chunks.parquet")


def _load_chunk_texts_by_article_id(
    chunks_path: Path,
    article_ids: list[str],
    pl: Any,
) -> dict[str, str]:
    if not chunks_path.is_file():
        logger.warning("legal_article_chunks parquet does not exist: %s", chunks_path)
        return {}

    chunks_df = pl.read_parquet(chunks_path)
    if "article_id" not in chunks_df.columns:
        logger.warning("legal_article_chunks parquet missing article_id column: %s", chunks_path)
        return {}

    text_column = _find_chunk_text_column(chunks_df.columns)
    if text_column is None:
        logger.warning("legal_article_chunks parquet missing text column: %s", chunks_path)
        return {}

    selected_columns = ["article_id", text_column]
    order_column = _find_chunk_order_column(chunks_df.columns)
    if order_column is not None:
        selected_columns.append(order_column)

    filtered_df = chunks_df.filter(pl.col("article_id").is_in(article_ids)).select(selected_columns)
    if order_column is not None:
        filtered_df = filtered_df.sort(["article_id", order_column])

    chunk_texts_by_article_id: dict[str, list[str]] = {}
    seen_texts_by_article_id: dict[str, set[str]] = {}
    for row in filtered_df.iter_rows(named=True):
        article_id = str(row.get("article_id") or "").strip()
        chunk_text = str(row.get(text_column) or "").strip()
        if not article_id or not chunk_text:
            continue

        seen_texts = seen_texts_by_article_id.setdefault(article_id, set())
        if chunk_text in seen_texts:
            continue

        # Ghép theo thứ tự chunk ổn định; bỏ duplicate để tránh prompt bị lặp đoạn.
        seen_texts.add(chunk_text)
        chunk_texts_by_article_id.setdefault(article_id, []).append(chunk_text)

    return {
        article_id: "\n\n".join(chunk_texts)
        for article_id, chunk_texts in chunk_texts_by_article_id.items()
        if chunk_texts
    }


def _find_chunk_text_column(columns: list[str]) -> str | None:
    for column in ("chunk_text", "text", "content_text", "article_text"):
        if column in columns:
            return column
    return None


def _find_chunk_order_column(columns: list[str]) -> str | None:
    for column in ("chunk_index", "chunk_no", "chunk_id"):
        if column in columns:
            return column
    return None


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _truncate_article_texts(
    articles: list[dict[str, Any]],
    max_article_chars: int | None,
    max_total_context_chars: int | None,
) -> list[dict[str, Any]]:
    if max_article_chars is None and max_total_context_chars is None:
        return articles

    per_article_limit = _normalize_limit(max_article_chars)
    total_limit = _normalize_limit(max_total_context_chars)
    total_chars = 0
    truncated_articles: list[dict[str, Any]] = []

    for article in articles:
        article_copy = dict(article)
        article_text = str(article_copy.get("article_text") or "")
        allowed_chars = len(article_text)

        if per_article_limit is not None:
            allowed_chars = min(allowed_chars, per_article_limit)

        if total_limit is not None:
            remaining_chars = max(total_limit - total_chars, 0)
            allowed_chars = min(allowed_chars, remaining_chars)

        truncated_text = _truncate_text(article_text, allowed_chars)
        article_copy["article_text"] = truncated_text
        total_chars += len(truncated_text)
        truncated_articles.append(article_copy)

    return truncated_articles


def _normalize_limit(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError("context character limits must be non-negative")
    return value


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    if max_chars <= 0:
        return ""

    if max_chars <= len(TRUNCATED_SUFFIX):
        return TRUNCATED_SUFFIX[:max_chars]

    content_limit = max_chars - len(TRUNCATED_SUFFIX)
    return text[:content_limit].rstrip() + TRUNCATED_SUFFIX
