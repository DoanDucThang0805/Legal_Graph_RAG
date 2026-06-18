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


def load_selected_article_contexts(
    article_ids: list[str],
    legal_articles_path: str | Path,
) -> list[dict[str, Any]]:
    """Hydrate canonical article IDs from legal_articles.parquet.

    Args:
        article_ids: Canonical article IDs in retrieval-selected order.
        legal_articles_path: Path to the canonical legal_articles parquet file.

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

    return [articles_by_id[article_id] for article_id in unique_article_ids if article_id in articles_by_id]


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
