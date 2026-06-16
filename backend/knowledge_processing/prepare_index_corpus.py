"""Prepare derived corpus files for indexing without changing canonical data."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

from backend.config.settings import get_settings
from backend.knowledge_processing.hf_loader import save_parquet
from backend.knowledge_processing.normalize_text import normalize_vietnamese_text

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 3000
DEFAULT_CHUNK_OVERLAP = 300

LEGAL_CHUNK_COLUMNS = [
    "chunk_id",
    "article_id",
    "law_id",
    "law_title",
    "article_no",
    "article_title",
    "chunk_index",
    "chunk_text",
    "article_text_len",
    "chunk_text_len",
    "source_url",
    "domain",
    "status",
]


def prepare_index_corpus(
    legal_articles_path: str | Path | None = None,
    phapdien_articles_path: str | Path | None = None,
    legal_chunks_output_path: str | Path | None = None,
    phapdien_index_output_path: str | Path | None = None,
    debug_dir: str | Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Build indexable derived corpus files for Phase 2."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    settings = get_settings()
    processed_dir = settings.paths.processed_dir
    debug_output_dir = Path(debug_dir) if debug_dir is not None else processed_dir / "debug"

    legal_source = (
        Path(legal_articles_path)
        if legal_articles_path is not None
        else processed_dir / "legal_articles.parquet"
    )
    phapdien_source = (
        Path(phapdien_articles_path)
        if phapdien_articles_path is not None
        else processed_dir / "phapdien_articles.parquet"
    )
    legal_target = (
        Path(legal_chunks_output_path)
        if legal_chunks_output_path is not None
        else processed_dir / "legal_article_chunks.parquet"
    )
    phapdien_target = (
        Path(phapdien_index_output_path)
        if phapdien_index_output_path is not None
        else processed_dir / "phapdien_articles_index.parquet"
    )

    legal_articles_df = pl.read_parquet(legal_source)
    phapdien_df = pl.read_parquet(phapdien_source)

    legal_chunks_df = build_legal_article_chunks(
        legal_articles_df,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    phapdien_index_df = build_phapdien_index_corpus(phapdien_df)

    debug_output_dir.mkdir(parents=True, exist_ok=True)
    write_legal_article_reports(legal_articles_df, legal_chunks_df, debug_output_dir)
    write_phapdien_empty_content_report(phapdien_df, debug_output_dir)

    save_parquet(legal_chunks_df, legal_target)
    save_parquet(phapdien_index_df, phapdien_target)

    logger.info(
        "Prepared index corpus: legal_chunks=%s phapdien_index=%s",
        legal_chunks_df.height,
        phapdien_index_df.height,
    )
    return legal_chunks_df, phapdien_index_df


def build_legal_article_chunks(
    legal_articles_df: pl.DataFrame,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> pl.DataFrame:
    """Build retrieval chunks while preserving parent article_id."""

    rows: list[dict[str, object]] = []
    for article in legal_articles_df.iter_rows(named=True):
        article_id = normalize_vietnamese_text(article.get("article_id"))
        article_text = normalize_vietnamese_text(article.get("article_text"))
        if not article_id or not article_text:
            logger.warning("Skipping article chunk with missing parent/text: article_id=%s", article_id)
            continue

        chunks = split_text_into_chunks(article_text, chunk_size, chunk_overlap)
        article_text_len = len(article_text)
        for chunk_index, chunk_text in enumerate(chunks):
            rows.append(
                {
                    "chunk_id": f"{article_id}|chunk:{chunk_index}",
                    "article_id": article_id,
                    "law_id": normalize_vietnamese_text(article.get("law_id")),
                    "law_title": normalize_vietnamese_text(article.get("law_title")),
                    "article_no": normalize_vietnamese_text(article.get("article_no")),
                    "article_title": normalize_vietnamese_text(article.get("article_title")),
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text,
                    "article_text_len": article_text_len,
                    "chunk_text_len": len(chunk_text),
                    "source_url": normalize_vietnamese_text(article.get("source_url")),
                    "domain": normalize_vietnamese_text(article.get("domain")),
                    "status": normalize_vietnamese_text(article.get("status")),
                }
            )

    if not rows:
        return pl.DataFrame(schema=_legal_chunk_schema())

    chunks_df = pl.DataFrame(rows).select(LEGAL_CHUNK_COLUMNS)
    duplicate_count = chunks_df.height - chunks_df["chunk_id"].n_unique()
    if duplicate_count:
        raise ValueError(f"Duplicate chunk_id detected: {duplicate_count}")
    return chunks_df


def split_text_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into bounded chunks with overlap for retrieval."""

    normalized = normalize_vietnamese_text(text)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    step = chunk_size - chunk_overlap
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized):
            break
        start += step
    return chunks


def build_phapdien_index_corpus(phapdien_df: pl.DataFrame) -> pl.DataFrame:
    """Filter phapdien rows with empty content_text for indexing only."""

    return phapdien_df.filter(pl.col("content_text").str.len_chars() > 0)


def write_legal_article_reports(
    legal_articles_df: pl.DataFrame,
    legal_chunks_df: pl.DataFrame,
    debug_dir: Path,
) -> None:
    """Write article length and chunk count reports."""

    length_report = (
        legal_articles_df.with_columns(
            pl.col("article_text").str.len_chars().alias("article_text_len")
        )
        .select("article_id", "law_id", "law_title", "article_no", "article_text_len")
        .sort("article_text_len", descending=True)
    )
    length_report.write_csv(debug_dir / "legal_article_text_length_report.csv")

    chunk_report = (
        legal_chunks_df.group_by("article_id")
        .agg(
            pl.len().alias("chunk_count"),
            pl.first("law_id").alias("law_id"),
            pl.first("law_title").alias("law_title"),
            pl.first("article_no").alias("article_no"),
            pl.first("article_title").alias("article_title"),
            pl.first("article_text_len").alias("article_text_len"),
            pl.max("chunk_text_len").alias("max_chunk_text_len"),
        )
        .sort(["chunk_count", "article_text_len"], descending=[True, True])
    )
    chunk_report.write_csv(debug_dir / "legal_article_chunk_report.csv")


def write_phapdien_empty_content_report(phapdien_df: pl.DataFrame, debug_dir: Path) -> None:
    """Write phapdien rows excluded from indexing because content_text is empty."""

    empty_df = phapdien_df.filter(pl.col("content_text").str.len_chars() == 0)
    empty_df.write_csv(debug_dir / "phapdien_empty_content_report.csv")


def _legal_chunk_schema() -> dict[str, pl.DataType]:
    return {
        "chunk_id": pl.Utf8,
        "article_id": pl.Utf8,
        "law_id": pl.Utf8,
        "law_title": pl.Utf8,
        "article_no": pl.Utf8,
        "article_title": pl.Utf8,
        "chunk_index": pl.Int64,
        "chunk_text": pl.Utf8,
        "article_text_len": pl.Int64,
        "chunk_text_len": pl.Int64,
        "source_url": pl.Utf8,
        "domain": pl.Utf8,
        "status": pl.Utf8,
    }
