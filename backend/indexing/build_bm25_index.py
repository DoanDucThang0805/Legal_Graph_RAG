"""Build OpenSearch BM25 indexes from processed parquet corpora."""

from __future__ import annotations

import logging
from hashlib import sha256
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import polars as pl

from backend.config.settings import get_settings
from backend.infrastructure.search_engine.opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)

LEGAL_ARTICLE_CHUNKS_INDEX = "legal_article_chunks_bm25"
PHAPDIEN_ARTICLES_INDEX = "phapdien_articles_bm25"
ANLE_UNITS_INDEX = "anle_units_bm25"

BULK_BATCH_SIZE = 500

LEGAL_ARTICLE_CHUNK_COLUMNS = [
    "chunk_id",
    "article_id",
    "law_id",
    "law_title",
    "article_no",
    "article_title",
    "chunk_index",
    "chunk_text",
    "source_url",
    "domain",
    "status",
]
PHAPDIEN_COLUMNS = [
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
ANLE_COLUMNS = [
    "unit_id",
    "text",
    "case_id",
    "title",
    "source_url",
    "metadata_json",
]


def build_all_bm25_indexes(
    *,
    recreate: bool = False,
    client: OpenSearchClient | None = None,
    processed_dir: str | Path | None = None,
) -> None:
    """Build all BM25 indexes used by baseline retrieval."""

    settings = get_settings()
    source_dir = Path(processed_dir) if processed_dir is not None else settings.paths.processed_dir
    search_client = client or OpenSearchClient()

    build_legal_article_chunks_bm25_index(
        source_dir / "legal_article_chunks.parquet",
        recreate=recreate,
        client=search_client,
    )
    build_phapdien_articles_bm25_index(
        source_dir / "phapdien_articles_index.parquet",
        recreate=recreate,
        client=search_client,
    )
    build_anle_units_bm25_index(
        source_dir / "anle_units.parquet",
        recreate=recreate,
        client=search_client,
    )


def build_legal_article_chunks_bm25_index(
    input_path: str | Path,
    *,
    recreate: bool = False,
    client: OpenSearchClient | None = None,
) -> None:
    """Build BM25 index for legal article chunks."""

    df = _read_required_parquet(input_path, LEGAL_ARTICLE_CHUNK_COLUMNS)
    _build_index_from_dataframe(
        df,
        index_name=LEGAL_ARTICLE_CHUNKS_INDEX,
        mapping=_legal_article_chunks_mapping(),
        id_column="chunk_id",
        recreate=recreate,
        client=client or OpenSearchClient(),
    )


def build_phapdien_articles_bm25_index(
    input_path: str | Path,
    *,
    recreate: bool = False,
    client: OpenSearchClient | None = None,
) -> None:
    """Build BM25 index for phapdien retrieval-only articles."""

    df = _read_required_parquet(input_path, PHAPDIEN_COLUMNS)
    _build_index_from_dataframe(
        df,
        index_name=PHAPDIEN_ARTICLES_INDEX,
        mapping=_phapdien_articles_mapping(),
        id_column="phapdien_id",
        recreate=recreate,
        client=client or OpenSearchClient(),
    )


def build_anle_units_bm25_index(
    input_path: str | Path,
    *,
    recreate: bool = False,
    client: OpenSearchClient | None = None,
) -> None:
    """Build BM25 index for anle auxiliary reasoning units."""

    df = _read_required_parquet(input_path, ANLE_COLUMNS)
    _build_index_from_dataframe(
        df,
        index_name=ANLE_UNITS_INDEX,
        mapping=_anle_units_mapping(),
        id_column="unit_id",
        recreate=recreate,
        client=client or OpenSearchClient(),
    )


def _build_index_from_dataframe(
    df: pl.DataFrame,
    *,
    index_name: str,
    mapping: dict[str, Any],
    id_column: str,
    recreate: bool,
    client: OpenSearchClient,
) -> None:
    sdk_client = client.client
    index_exists = bool(sdk_client.indices.exists(index=index_name))

    if index_exists and recreate:
        logger.info("Deleting existing BM25 index: %s", index_name)
        sdk_client.indices.delete(index=index_name)
        index_exists = False

    if not index_exists:
        logger.info("Creating BM25 index: %s", index_name)
        sdk_client.indices.create(index=index_name, body=mapping)

    indexed_count = _bulk_index_dataframe(
        sdk_client,
        index_name=index_name,
        df=df,
        id_column=id_column,
    )
    sdk_client.indices.refresh(index=index_name)
    logger.info("BM25 index built: index=%s rows=%s", index_name, indexed_count)


def _bulk_index_dataframe(
    sdk_client: Any,
    *,
    index_name: str,
    df: pl.DataFrame,
    id_column: str,
) -> int:
    try:
        from opensearchpy.helpers import bulk
    except ImportError as exc:
        raise RuntimeError("Missing dependency: opensearch-py") from exc

    total_indexed = 0
    for actions in _iter_bulk_actions(df, index_name=index_name, id_column=id_column):
        success_count, _ = bulk(sdk_client, actions, raise_on_error=True)
        total_indexed += int(success_count)
    return total_indexed


def _iter_bulk_actions(
    df: pl.DataFrame,
    *,
    index_name: str,
    id_column: str,
) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in df.iter_rows(named=True):
        document_id = _build_opensearch_document_id(row.get(id_column), id_column)
        batch.append(
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": document_id,
                "_source": _clean_source(row),
            }
        )
        if len(batch) >= BULK_BATCH_SIZE:
            yield batch
            batch = []

    if batch:
        yield batch


def _read_required_parquet(input_path: str | Path, required_columns: list[str]) -> pl.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"BM25 source parquet not found: {path}")

    df = pl.read_parquet(path)
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in {path}: {missing_columns}")

    return df.select(required_columns)


def _normalize_document_id(value: Any, column_name: str) -> str:
    document_id = "" if value is None else str(value).strip()
    if not document_id:
        raise ValueError(f"Empty document id for OpenSearch column: {column_name}")
    return document_id


def _build_opensearch_document_id(value: Any, column_name: str) -> str:
    canonical_id = _normalize_document_id(value, column_name)
    # OpenSearch giới hạn _id tối đa 512 bytes. Giữ canonical id trong _source,
    # chỉ hash _id nội bộ để bulk index không lỗi với law_title rất dài.
    return sha256(canonical_id.encode("utf-8")).hexdigest()


def _clean_source(row: dict[str, Any]) -> dict[str, Any]:
    return {key: "" if value is None else value for key, value in row.items()}


def _base_index_settings() -> dict[str, Any]:
    return {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        }
    }


def _keyword_field() -> dict[str, str]:
    return {"type": "keyword"}


def _text_field() -> dict[str, str]:
    return {"type": "text"}


def _legal_article_chunks_mapping() -> dict[str, Any]:
    mapping = _base_index_settings()
    mapping["mappings"] = {
        "properties": {
            "chunk_id": _keyword_field(),
            "article_id": _keyword_field(),
            "law_id": _keyword_field(),
            "law_title": _text_with_keyword(),
            "article_no": _keyword_field(),
            "article_title": _text_field(),
            "chunk_index": {"type": "integer"},
            "chunk_text": _text_field(),
            "source_url": _keyword_field(),
            "domain": _keyword_field(),
            "status": _keyword_field(),
        }
    }
    return mapping


def _phapdien_articles_mapping() -> dict[str, Any]:
    mapping = _base_index_settings()
    mapping["mappings"] = {
        "properties": {
            "phapdien_id": _keyword_field(),
            "topic_title": _text_with_keyword(),
            "subject_title": _text_with_keyword(),
            "chapter_title": _text_field(),
            "article_title": _text_field(),
            "content_text": _text_field(),
            "source_note_text": _text_field(),
            "related_note_text": _text_field(),
            "source_url": _keyword_field(),
            "source_links_json": _text_field(),
        }
    }
    return mapping


def _anle_units_mapping() -> dict[str, Any]:
    mapping = _base_index_settings()
    mapping["mappings"] = {
        "properties": {
            "unit_id": _keyword_field(),
            "text": _text_field(),
            "case_id": _keyword_field(),
            "title": _text_with_keyword(),
            "source_url": _keyword_field(),
            "metadata_json": _text_field(),
        }
    }
    return mapping


def _text_with_keyword() -> dict[str, Any]:
    return {
        "type": "text",
        "fields": {
            "keyword": {
                "type": "keyword",
                "ignore_above": 512,
            }
        },
    }
