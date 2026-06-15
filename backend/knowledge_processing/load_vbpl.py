"""Loader for canonical VBPL document-level corpus."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

from backend.config.settings import get_settings
from backend.knowledge_processing.hf_loader import load_hf_dataset_to_polars, save_parquet
from backend.knowledge_processing.normalize_text import (
    normalize_law_id,
    normalize_law_title,
    normalize_law_type,
    normalize_vietnamese_text,
)

logger = logging.getLogger(__name__)

VBPL_DATASET = "tmquan/vbpl-vn"
VBPL_CONFIG: str | None = None
VBPL_SPLIT = "train"

OUTPUT_COLUMNS = [
    "doc_id",
    "law_id",
    "law_type",
    "law_title",
    "normalized_title",
    "source_url",
    "markdown",
    "issue_date",
    "effective_date",
    "status",
    "legal_area",
]

DOC_ID_CANDIDATES = ["doc_id", "document_id", "id", "vbpl_id", "doc_name", "item_id"]
LAW_ID_CANDIDATES = ["law_id", "code", "document_code", "number", "so_hieu", "doc_number"]
LAW_TYPE_CANDIDATES = [
    "law_type",
    "document_type",
    "type",
    "loai_van_ban",
    "doc_type",
    "legal_type",
]
TITLE_CANDIDATES = ["law_title", "title", "document_title", "trich_yeu", "summary"]
MARKDOWN_CANDIDATES = ["markdown", "body", "text", "content", "full_text", "html_text"]
SOURCE_URL_CANDIDATES = ["source_url", "url", "href", "api_url"]
ISSUE_DATE_CANDIDATES = ["issue_date", "issued_date", "ngay_ban_hanh"]
EFFECTIVE_DATE_CANDIDATES = ["effective_date", "ngay_hieu_luc", "valid_from"]
STATUS_CANDIDATES = ["status", "effect_status", "tinh_trang"]
LEGAL_AREA_CANDIDATES = ["legal_area", "domain", "field", "linh_vuc"]


def load_vbpl_documents(output_path: str | Path | None = None) -> pl.DataFrame:
    """Load VBPL documents from Hugging Face and save normalized parquet."""

    settings = get_settings()
    target_path = (
        Path(output_path)
        if output_path is not None
        else settings.paths.processed_dir / "legal_documents.parquet"
    )

    raw_df = load_hf_dataset_to_polars(VBPL_DATASET, VBPL_CONFIG, VBPL_SPLIT)
    normalized_df = normalize_vbpl_dataframe(raw_df)
    save_parquet(normalized_df, target_path)
    logger.info("Loaded VBPL documents: rows=%s output=%s", normalized_df.height, target_path)
    return normalized_df


def normalize_vbpl_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize raw VBPL rows into canonical document-level records."""

    if df.is_empty():
        raise ValueError("VBPL dataset is empty")

    law_id_column = _first_existing_column(df, LAW_ID_CANDIDATES)
    title_column = _first_existing_column(df, TITLE_CANDIDATES)
    markdown_column = _first_existing_column(df, MARKDOWN_CANDIDATES)

    if law_id_column is None:
        raise ValueError(f"VBPL dataset has no law_id column. columns={df.columns}")
    if markdown_column is None:
        raise ValueError(f"VBPL dataset has no markdown/body column. columns={df.columns}")

    law_type_column = _first_existing_column(df, LAW_TYPE_CANDIDATES)
    doc_id_column = _first_existing_column(df, DOC_ID_CANDIDATES)

    law_ids = _normalized_series(df, law_id_column, "law_id").to_list()
    law_types = _optional_law_type_series(df, law_type_column).to_list()
    raw_titles = _optional_normalized_series(df, title_column, "raw_title").to_list()
    law_titles = [
        normalize_law_title(law_type, law_id, title)
        for law_type, law_id, title in zip(law_types, law_ids, raw_titles, strict=True)
    ]

    output_df = pl.DataFrame(
        {
            "doc_id": _build_doc_ids(df, doc_id_column, law_ids),
            "law_id": pl.Series("law_id", law_ids, dtype=pl.Utf8),
            "law_type": pl.Series("law_type", law_types, dtype=pl.Utf8),
            "law_title": pl.Series("law_title", law_titles, dtype=pl.Utf8),
            "normalized_title": pl.Series(
                "normalized_title",
                [normalize_vietnamese_text(value) for value in law_titles],
                dtype=pl.Utf8,
            ),
            "source_url": _optional_normalized_series(
                df,
                _first_existing_column(df, SOURCE_URL_CANDIDATES),
                "source_url",
            ),
            "markdown": _normalized_series(df, markdown_column, "markdown"),
            "issue_date": _optional_normalized_series(
                df,
                _first_existing_column(df, ISSUE_DATE_CANDIDATES),
                "issue_date",
            ),
            "effective_date": _optional_normalized_series(
                df,
                _first_existing_column(df, EFFECTIVE_DATE_CANDIDATES),
                "effective_date",
            ),
            "status": _optional_normalized_series(
                df,
                _first_existing_column(df, STATUS_CANDIDATES),
                "status",
            ),
            "legal_area": _optional_normalized_series(
                df,
                _first_existing_column(df, LEGAL_AREA_CANDIDATES),
                "legal_area",
            ),
        }
    )

    valid_df = _filter_invalid_documents(output_df)
    _validate_output(valid_df)
    return valid_df.select(OUTPUT_COLUMNS)


def _first_existing_column(df: pl.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _normalized_series(df: pl.DataFrame, source_column: str, output_name: str) -> pl.Series:
    return df[source_column].map_elements(_normalize_cell_text, return_dtype=pl.Utf8).alias(
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


def _optional_law_type_series(df: pl.DataFrame, source_column: str | None) -> pl.Series:
    if source_column is None:
        return pl.Series("law_type", [""] * df.height, dtype=pl.Utf8)
    return df[source_column].map_elements(
        lambda value: normalize_law_type(_flatten_text_value(value)),
        return_dtype=pl.Utf8,
    ).alias("law_type")


def _normalize_cell_text(value: Any) -> str:
    """Flatten nested Polars/list/dict cells before text normalization."""

    return normalize_vietnamese_text(_flatten_text_value(value))


def _flatten_text_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, pl.Series):
        if value.len() == 0:
            return ""
        if value.len() == 1:
            return _flatten_text_value(value.item(0))
        return " ".join(
            item
            for item in (_flatten_text_value(cell) for cell in value.to_list())
            if item
        )

    if isinstance(value, list | tuple):
        return " ".join(
            item
            for item in (_flatten_text_value(cell) for cell in value)
            if item
        )

    if isinstance(value, dict):
        for key in ("text", "value", "number", "title", "name", "href"):
            if key in value:
                text = _flatten_text_value(value[key])
                if text:
                    return text
        return " ".join(
            item
            for item in (_flatten_text_value(cell) for cell in value.values())
            if item
        )

    return str(value)


def _build_doc_ids(
    df: pl.DataFrame,
    doc_id_column: str | None,
    law_ids: list[str],
) -> pl.Series:
    if doc_id_column is not None:
        raw_doc_ids = _normalized_series(df, doc_id_column, "doc_id").to_list()
    else:
        raw_doc_ids = [""] * df.height

    values = [
        doc_id or law_id or f"vbpl:{index}"
        for index, (doc_id, law_id) in enumerate(zip(raw_doc_ids, law_ids, strict=True))
    ]
    return pl.Series("doc_id", values, dtype=pl.Utf8)


def _filter_invalid_documents(df: pl.DataFrame) -> pl.DataFrame:
    invalid_df = df.filter(
        (pl.col("law_id").str.len_chars() == 0)
        | (pl.col("law_title").str.len_chars() == 0)
        | (pl.col("markdown").str.len_chars() == 0)
    )

    if invalid_df.height:
        logger.warning("Skipping invalid VBPL documents: count=%s", invalid_df.height)
        for row in invalid_df.select("doc_id", "law_id", "law_title").head(20).iter_rows(named=True):
            logger.warning("Invalid VBPL document sample: %s", row)

    return df.filter(
        (pl.col("law_id").str.len_chars() > 0)
        & (pl.col("law_title").str.len_chars() > 0)
        & (pl.col("markdown").str.len_chars() > 0)
    )


def _validate_output(df: pl.DataFrame) -> None:
    missing_columns = [column for column in OUTPUT_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing VBPL output columns: {missing_columns}")

    if df.is_empty():
        raise ValueError("No valid VBPL documents after normalization")

    duplicate_count = df.height - df["doc_id"].n_unique()
    if duplicate_count:
        logger.warning("VBPL documents with duplicate doc_id: count=%s", duplicate_count)
