"""Loader for the anle auxiliary reasoning corpus."""

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

ANLE_DATASET = "tmquan/anle-toaan-gov-vn"
ANLE_CONFIG = "sentences"
ANLE_SPLIT = "train"

OUTPUT_COLUMNS = [
    "unit_id",
    "text",
    "case_id",
    "title",
    "source_url",
    "metadata_json",
]

TEXT_COLUMN_CANDIDATES = ["text", "sentence", "content", "paragraph"]
CASE_ID_CANDIDATES = ["case_id", "anle_id", "doc_id", "id"]
TITLE_CANDIDATES = ["title", "case_title", "name"]
SOURCE_URL_CANDIDATES = ["source_url", "url", "href"]


def load_anle_sentences(output_path: str | Path | None = None) -> pl.DataFrame:
    """Load anle sentence units from Hugging Face and save normalized parquet."""

    settings = get_settings()
    target_path = (
        Path(output_path)
        if output_path is not None
        else settings.paths.processed_dir / "anle_units.parquet"
    )

    raw_df = load_hf_dataset_to_polars(ANLE_DATASET, ANLE_CONFIG, ANLE_SPLIT)
    normalized_df = normalize_anle_dataframe(raw_df)
    save_parquet(normalized_df, target_path)

    logger.info(
        "Loaded anle units: rows=%s output=%s. anle is auxiliary-only, not official citation.",
        normalized_df.height,
        target_path,
    )
    return normalized_df


def normalize_anle_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize raw anle rows into sentence-level auxiliary units."""

    if df.is_empty():
        raise ValueError("anle dataset is empty")

    text_column = _first_existing_column(df, TEXT_COLUMN_CANDIDATES)
    if text_column is None:
        raise ValueError(f"anle dataset has no text column. columns={df.columns}")

    case_id_column = _first_existing_column(df, CASE_ID_CANDIDATES)
    title_column = _first_existing_column(df, TITLE_CANDIDATES)
    source_url_column = _first_existing_column(df, SOURCE_URL_CANDIDATES)

    output_df = pl.DataFrame(
        {
            "unit_id": _build_unit_ids(df, case_id_column),
            "text": _normalized_series(df, text_column, "text"),
            "case_id": _optional_normalized_series(df, case_id_column, "case_id"),
            "title": _optional_normalized_series(df, title_column, "title"),
            "source_url": _optional_normalized_series(df, source_url_column, "source_url"),
            "metadata_json": _metadata_series(df),
        }
    )

    output_df = output_df.filter(pl.col("text").str.len_chars() > 0)
    _validate_output(output_df)
    return output_df.select(OUTPUT_COLUMNS)


def _first_existing_column(df: pl.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _normalized_series(df: pl.DataFrame, source_column: str, output_name: str) -> pl.Series:
    return df[source_column].map_elements(normalize_vietnamese_text, return_dtype=pl.Utf8).alias(
        output_name
    )


def _optional_normalized_series(
    df: pl.DataFrame,
    source_column: str | None,
    output_name: str,
) -> pl.Series:
    if source_column is None:
        return pl.Series(output_name, [""] * df.height, dtype=pl.Utf8)
    return _normalized_series(df, source_column, output_name)


def _build_unit_ids(df: pl.DataFrame, case_id_column: str | None) -> pl.Series:
    if case_id_column is None:
        return pl.Series("unit_id", [f"anle:{index}" for index in range(df.height)], dtype=pl.Utf8)

    case_ids = df[case_id_column].map_elements(normalize_vietnamese_text, return_dtype=pl.Utf8)
    values = [
        f"{case_id or 'anle'}:{index}"
        for index, case_id in enumerate(case_ids.to_list())
    ]
    return pl.Series("unit_id", values, dtype=pl.Utf8)


def _metadata_series(df: pl.DataFrame) -> pl.Series:
    metadata_columns = [
        column
        for column in df.columns
        if not _is_embedding_column(column)
    ]
    metadata_values: list[str] = []

    for row in df.select(metadata_columns).iter_rows(named=True):
        metadata_values.append(json.dumps(_to_jsonable(row), ensure_ascii=False))

    return pl.Series("metadata_json", metadata_values, dtype=pl.Utf8)


def _is_embedding_column(column: str) -> bool:
    lowered = column.casefold()
    return "embedding" in lowered or lowered in {"vector", "vectors"}


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, pl.Series):
        return [_to_jsonable(item) for item in value.to_list()]
    return value


def _validate_output(df: pl.DataFrame) -> None:
    missing_columns = [column for column in OUTPUT_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing anle output columns: {missing_columns}")

    duplicate_count = df.height - df["unit_id"].n_unique()
    if duplicate_count:
        raise ValueError(f"anle unit_id must be unique. duplicates={duplicate_count}")

    empty_text_count = df.filter(pl.col("text").str.len_chars() == 0).height
    if empty_text_count:
        raise ValueError(f"anle rows with empty text after filtering: {empty_text_count}")
