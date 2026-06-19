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
) -> list[dict[str, Any]]:
    """Hydrate canonical article IDs from legal_articles.parquet.

    Args:
        article_ids: Canonical article IDs in retrieval-selected order.
        legal_articles_path: Path to the canonical legal_articles parquet file.
        max_article_chars: Optional per-article article_text character limit.
        max_total_context_chars: Optional total article_text character budget.

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
    return _truncate_article_texts(
        ordered_articles,
        max_article_chars=max_article_chars,
        max_total_context_chars=max_total_context_chars,
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
