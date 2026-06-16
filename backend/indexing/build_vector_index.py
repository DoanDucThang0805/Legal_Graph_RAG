"""Build Qdrant dense vector indexes from processed parquet corpora."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import polars as pl

from backend.config.settings import get_settings
from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder
from backend.infrastructure.vector_store.qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

LEGAL_ARTICLES_COLLECTION = "legal_articles_dense"
PHAPDIEN_ARTICLES_COLLECTION = "phapdien_articles_dense"
ANLE_UNITS_COLLECTION = "anle_units_dense"

UPSERT_BATCH_SIZE = 128

LEGAL_ARTICLE_COLUMNS = [
    "article_id",
    "law_id",
    "law_title",
    "article_no",
    "article_title",
    "article_text",
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


def build_all_vector_indexes(
    *,
    recreate: bool = False,
    skip_existing: bool = False,
    max_rows: int | None = None,
    resume: bool = False,
    client: QdrantClient | None = None,
    embedder: VNLegalLALEmbedder | None = None,
    processed_dir: str | Path | None = None,
) -> None:
    """Build all Qdrant vector collections for dense retrieval."""

    settings = get_settings()
    source_dir = Path(processed_dir) if processed_dir is not None else settings.paths.processed_dir
    vector_client = client or QdrantClient()
    embedding_model = embedder or VNLegalLALEmbedder()

    build_legal_articles_vector_index(
        source_dir / "legal_articles.parquet",
        recreate=recreate,
        skip_existing=skip_existing,
        max_rows=max_rows,
        resume=resume,
        client=vector_client,
        embedder=embedding_model,
    )
    build_phapdien_articles_vector_index(
        source_dir / "phapdien_articles.parquet",
        recreate=recreate,
        skip_existing=skip_existing,
        max_rows=max_rows,
        resume=resume,
        client=vector_client,
        embedder=embedding_model,
    )
    build_anle_units_vector_index(
        source_dir / "anle_units.parquet",
        recreate=recreate,
        skip_existing=skip_existing,
        max_rows=max_rows,
        resume=resume,
        client=vector_client,
        embedder=embedding_model,
    )


def build_legal_articles_vector_index(
    input_path: str | Path,
    *,
    recreate: bool = False,
    skip_existing: bool = False,
    max_rows: int | None = None,
    resume: bool = False,
    client: QdrantClient | None = None,
    embedder: VNLegalLALEmbedder | None = None,
) -> None:
    """Build vector collection for canonical legal articles."""

    df = _limit_dataframe(_read_required_parquet(input_path, LEGAL_ARTICLE_COLUMNS), max_rows)
    _build_collection_from_dataframe(
        df,
        collection_name=LEGAL_ARTICLES_COLLECTION,
        id_column="article_id",
        text_builder=_build_legal_article_text,
        recreate=recreate,
        skip_existing=skip_existing,
        resume=resume,
        client=client or QdrantClient(),
        embedder=embedder or VNLegalLALEmbedder(),
    )


def build_phapdien_articles_vector_index(
    input_path: str | Path,
    *,
    recreate: bool = False,
    skip_existing: bool = False,
    max_rows: int | None = None,
    resume: bool = False,
    client: QdrantClient | None = None,
    embedder: VNLegalLALEmbedder | None = None,
) -> None:
    """Build vector collection for phapdien retrieval-only articles."""

    df = _limit_dataframe(_read_required_parquet(input_path, PHAPDIEN_COLUMNS), max_rows)
    _build_collection_from_dataframe(
        df,
        collection_name=PHAPDIEN_ARTICLES_COLLECTION,
        id_column="phapdien_id",
        text_builder=_build_phapdien_text,
        recreate=recreate,
        skip_existing=skip_existing,
        resume=resume,
        client=client or QdrantClient(),
        embedder=embedder or VNLegalLALEmbedder(),
    )


def build_anle_units_vector_index(
    input_path: str | Path,
    *,
    recreate: bool = False,
    skip_existing: bool = False,
    max_rows: int | None = None,
    resume: bool = False,
    client: QdrantClient | None = None,
    embedder: VNLegalLALEmbedder | None = None,
) -> None:
    """Build vector collection for anle auxiliary reasoning units."""

    df = _limit_dataframe(_read_required_parquet(input_path, ANLE_COLUMNS), max_rows)
    _build_collection_from_dataframe(
        df,
        collection_name=ANLE_UNITS_COLLECTION,
        id_column="unit_id",
        text_builder=_build_anle_text,
        recreate=recreate,
        skip_existing=skip_existing,
        resume=resume,
        client=client or QdrantClient(),
        embedder=embedder or VNLegalLALEmbedder(),
    )


def _build_collection_from_dataframe(
    df: pl.DataFrame,
    *,
    collection_name: str,
    id_column: str,
    text_builder: Callable[[dict[str, Any]], str],
    recreate: bool,
    skip_existing: bool,
    resume: bool,
    client: QdrantClient,
    embedder: VNLegalLALEmbedder,
) -> None:
    sdk_client = client.client
    collection_exists = _collection_exists(sdk_client, collection_name)

    if collection_exists and skip_existing and not recreate:
        logger.info("Skipping existing vector collection: %s", collection_name)
        return

    if collection_exists and recreate:
        logger.info("Deleting existing vector collection: %s", collection_name)
        sdk_client.delete_collection(collection_name=collection_name)
        collection_exists = False

    if not collection_exists:
        logger.info("Creating vector collection: %s", collection_name)
        _create_collection(sdk_client, collection_name, embedder.expected_dimension)

    indexed_count = _upsert_dataframe(
        sdk_client,
        collection_name=collection_name,
        df=df,
        id_column=id_column,
        text_builder=text_builder,
        embedder=embedder,
        resume=resume,
    )
    logger.info("Vector collection built: collection=%s rows=%s", collection_name, indexed_count)


def _upsert_dataframe(
    sdk_client: Any,
    *,
    collection_name: str,
    df: pl.DataFrame,
    id_column: str,
    text_builder: Callable[[dict[str, Any]], str],
    embedder: VNLegalLALEmbedder,
    resume: bool,
) -> int:
    try:
        from qdrant_client.models import PointStruct
        from tqdm import tqdm
    except ImportError as exc:
        raise RuntimeError("Missing dependency: qdrant-client or tqdm") from exc

    total_indexed = 0
    total_skipped = 0
    total_scanned = 0
    total_batches = (df.height + UPSERT_BATCH_SIZE - 1) // UPSERT_BATCH_SIZE
    progress = tqdm(
        _iter_row_batches(df, UPSERT_BATCH_SIZE),
        total=total_batches,
        desc=f"Indexing {collection_name}",
        unit="batch",
    )
    for rows in progress:
        total_scanned += len(rows)
        row_id_pairs = [(row, _build_point_id(row[id_column])) for row in rows]
        if resume:
            row_id_pairs, skipped_count = _filter_missing_points(
                sdk_client,
                collection_name=collection_name,
                row_id_pairs=row_id_pairs,
            )
            total_skipped += skipped_count

        if not row_id_pairs:
            progress.set_postfix(scanned=total_scanned, indexed=total_indexed, skipped=total_skipped)
            continue

        texts = [text_builder(row) for row, _ in row_id_pairs]
        vectors = embedder.encode_documents(texts)
        points = [
            PointStruct(
                id=point_id,
                vector=vector,
                payload=_clean_payload(row),
            )
            for (row, point_id), vector in zip(row_id_pairs, vectors, strict=True)
        ]
        sdk_client.upsert(collection_name=collection_name, points=points, wait=True)
        total_indexed += len(points)
        progress.set_postfix(scanned=total_scanned, indexed=total_indexed, skipped=total_skipped)
        logger.info(
            "Upserted vector batch: collection=%s scanned=%s indexed=%s skipped=%s",
            collection_name,
            total_scanned,
            total_indexed,
            total_skipped,
        )

    return total_indexed


def _filter_missing_points(
    sdk_client: Any,
    *,
    collection_name: str,
    row_id_pairs: list[tuple[dict[str, Any], str]],
) -> tuple[list[tuple[dict[str, Any], str]], int]:
    point_ids = [point_id for _, point_id in row_id_pairs]
    existing_points = sdk_client.retrieve(
        collection_name=collection_name,
        ids=point_ids,
        with_payload=False,
        with_vectors=False,
    )
    existing_ids = {str(point.id) for point in existing_points}
    missing_pairs = [
        (row, point_id)
        for row, point_id in row_id_pairs
        if point_id not in existing_ids
    ]
    return missing_pairs, len(row_id_pairs) - len(missing_pairs)


def _create_collection(sdk_client: Any, collection_name: str, vector_size: int) -> None:
    try:
        from qdrant_client.models import Distance, VectorParams
    except ImportError as exc:
        raise RuntimeError("Missing dependency: qdrant-client") from exc

    sdk_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def _collection_exists(sdk_client: Any, collection_name: str) -> bool:
    collections = sdk_client.get_collections().collections
    return any(collection.name == collection_name for collection in collections)


def _read_required_parquet(input_path: str | Path, required_columns: list[str]) -> pl.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Vector source parquet not found: {path}")

    df = pl.read_parquet(path)
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in {path}: {missing_columns}")

    return df.select(required_columns)


def _limit_dataframe(df: pl.DataFrame, max_rows: int | None) -> pl.DataFrame:
    if max_rows is None:
        return df
    if max_rows <= 0:
        raise ValueError("max_rows must be positive when provided")
    return df.head(max_rows)


def _iter_row_batches(df: pl.DataFrame, batch_size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in df.iter_rows(named=True):
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _build_point_id(value: Any) -> str:
    canonical_id = _required_text(value, "point_id")
    # Qdrant string point ids must be UUIDs. UUIDv5 is deterministic while
    # preserving the canonical id inside payload for retrieval/citation logic.
    return str(uuid5(NAMESPACE_URL, canonical_id))


def _clean_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {key: "" if value is None else value for key, value in row.items()}


def _build_legal_article_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Tên văn bản: {_optional_text(row.get('law_title'))}",
            f"Điều: {_optional_text(row.get('article_no'))}",
            f"Tiêu đề điều: {_optional_text(row.get('article_title'))}",
            "Nội dung:",
            _required_text(row.get("article_text"), "article_text"),
        ]
    )


def _build_phapdien_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Chủ đề: {_optional_text(row.get('topic_title'))}",
            f"Đề mục: {_optional_text(row.get('subject_title'))}",
            f"Chương: {_optional_text(row.get('chapter_title'))}",
            f"Điều pháp điển: {_optional_text(row.get('article_title'))}",
            f"Nguồn gốc: {_optional_text(row.get('source_note_text'))}",
            "Nội dung:",
            _required_text(row.get("content_text"), "content_text"),
            "Liên quan:",
            _optional_text(row.get("related_note_text")),
        ]
    )


def _build_anle_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Án lệ/Tình huống: {_optional_text(row.get('title'))}",
            "Nội dung:",
            _required_text(row.get("text"), "text"),
        ]
    )


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _required_text(value: Any, field_name: str) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError(f"Missing required text for vector indexing: {field_name}")
    return text
