"""Loader for the phapdien retrieval corpus."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from backend.config.settings import get_settings
from backend.knowledge_processing.hf_loader import load_hf_dataset_to_polars, save_parquet
from backend.knowledge_processing.normalize_text import normalize_vietnamese_text

logger = logging.getLogger(__name__)

PHAPDIEN_DATASET = "tmquan/phapdien-moj-gov-vn"
PHAPDIEN_CONFIG = "articles"
PHAPDIEN_SPLIT = "train"

REQUIRED_COLUMNS = [
    "phapdien_id",
    "topic_title",
    "subject_title",
    "chapter_title",
    "article_title",
    "content_text",
    "source_note_text",
    "related_note_text",
    "source_url",
    "source_links_json",
]


def load_phapdien_articles(output_path: str | Path | None = None) -> pl.DataFrame:
    """Load phapdien articles from Hugging Face and save normalized parquet."""

    settings = get_settings()
    target_path = (
        Path(output_path)
        if output_path is not None
        else settings.paths.processed_dir / "phapdien_articles.parquet"
    )

    raw_df = load_hf_dataset_to_polars(PHAPDIEN_DATASET, PHAPDIEN_CONFIG, PHAPDIEN_SPLIT)
    normalized_df = normalize_phapdien_dataframe(raw_df)
    save_parquet(normalized_df, target_path)

    logger.info(
        "Loaded phapdien articles: rows=%s output=%s. "
        "article_title is retrieval-only, not official citation.",
        normalized_df.height,
        target_path,
    )
    return normalized_df


def normalize_phapdien_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize the raw phapdien DataFrame into project-required columns."""

    if df.is_empty():
        raise ValueError("phapdien dataset is empty")

    working_df = _ensure_phapdien_id(df)
    output_columns: dict[str, pl.Series] = {}

    for column in REQUIRED_COLUMNS:
        if column == "source_links_json":
            output_columns[column] = _source_links_series(working_df)
            continue

        source_column = column
        if source_column not in working_df.columns:
            output_columns[column] = pl.Series(column, [""] * working_df.height, dtype=pl.Utf8)
            continue

        output_columns[column] = working_df[source_column].map_elements(
            normalize_vietnamese_text,
            return_dtype=pl.Utf8,
        ).alias(column)

    output_df = pl.DataFrame(output_columns)
    _validate_required_output(output_df)
    return output_df.select(REQUIRED_COLUMNS)


def _ensure_phapdien_id(df: pl.DataFrame) -> pl.DataFrame:
    if "phapdien_id" in df.columns:
        return df

    if "article_id" in df.columns:
        return df.with_columns(
            pl.col("article_id")
            .map_elements(normalize_vietnamese_text, return_dtype=pl.Utf8)
            .alias("phapdien_id")
        )

    logger.warning("phapdien source has no article_id; falling back to row-based phapdien_id")
    return df.with_row_index("phapdien_row").with_columns(
        pl.format("phapdien:{}", pl.col("phapdien_row")).alias("phapdien_id")
    )


def _source_links_series(df: pl.DataFrame) -> pl.Series:
    if "source_links" not in df.columns:
        return pl.Series("source_links_json", [""] * df.height, dtype=pl.Utf8)

    return df["source_links"].map_elements(_json_dumps_safe, return_dtype=pl.Utf8).alias(
        "source_links_json"
    )


def _json_dumps_safe(value: Any) -> str:
    if value is None:
        return ""

    normalized_value = _to_jsonable(value)
    try:
        return json.dumps(normalized_value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(normalized_value), ensure_ascii=False)


def _to_jsonable(value: Any) -> Any:
    """Convert nested Polars values to plain Python objects before JSON dump."""

    if isinstance(value, pl.Series):
        if value.len() == 0:
            return []
        if value.len() == 1:
            return _to_jsonable(value.item(0))
        return [_to_jsonable(item) for item in value.to_list()]

    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}

    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]

    return value


def _validate_required_output(df: pl.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing phapdien output columns: {missing_columns}")

    empty_content_count = df.filter(pl.col("content_text").str.len_chars() == 0).height
    if empty_content_count:
        logger.warning("phapdien rows with empty content_text: count=%s", empty_content_count)

    empty_id_count = df.filter(pl.col("phapdien_id").str.len_chars() == 0).height
    if empty_id_count:
        raise ValueError(f"phapdien rows with empty phapdien_id: {empty_id_count}")
