"""Build Neo4j legal graph index from canonical processed parquet files."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import polars as pl

from backend.config.settings import get_settings
from backend.infrastructure.graph_store.neo4j_client import Neo4jClient
from backend.knowledge_processing.normalize_text import normalize_article_no, normalize_vietnamese_text

logger = logging.getLogger(__name__)

LEGAL_ARTICLE_COLUMNS = [
    "article_id",
    "law_id",
    "law_title",
    "article_no",
    "article_title",
    "source_url",
    "domain",
    "status",
]

PHAPDIEN_MAPPING_COLUMNS = [
    "phapdien_id",
    "legal_article_id",
    "law_id",
    "law_title",
    "article_no",
    "mapping_score",
    "mapping_method",
]

VALID_BUILD_MODES = {"upsert", "recreate"}
DEFAULT_BATCH_SIZE = 1_000

CONSTRAINT_QUERIES = [
    """
    CREATE CONSTRAINT law_law_id_unique IF NOT EXISTS
    FOR (law:Law) REQUIRE law.law_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT article_article_id_unique IF NOT EXISTS
    FOR (article:Article) REQUIRE article.article_id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT phapdien_article_id_unique IF NOT EXISTS
    FOR (article:PhapdienArticle) REQUIRE article.phapdien_id IS UNIQUE
    """,
]

RECREATE_QUERY = """
MATCH (node)
WHERE node:Law OR node:Article OR node:PhapdienArticle
DETACH DELETE node
"""

UPSERT_ARTICLE_GRAPH_QUERY = """
UNWIND $rows AS row
MERGE (law:Law {law_id: row.law_id})
SET
    law.law_title = row.law_title,
    law.updated_at = datetime()
MERGE (article:Article {article_id: row.article_id})
SET
    article.law_id = row.law_id,
    article.law_title = row.law_title,
    article.article_no = row.article_no,
    article.article_title = row.article_title,
    article.source_url = row.source_url,
    article.domain = row.domain,
    article.status = row.status,
    article.updated_at = datetime()
MERGE (law)-[:HAS_ARTICLE]->(article)
"""

UPSERT_PHAPDIEN_MAPPING_QUERY = """
UNWIND $rows AS row
MERGE (phapdien:PhapdienArticle {phapdien_id: row.phapdien_id})
SET
    phapdien.legal_article_id = row.legal_article_id,
    phapdien.law_id = row.law_id,
    phapdien.law_title = row.law_title,
    phapdien.article_no = row.article_no,
    phapdien.mapping_score = row.mapping_score,
    phapdien.mapping_method = row.mapping_method,
    phapdien.updated_at = datetime()
WITH phapdien, row
MATCH (article:Article {article_id: row.legal_article_id})
MERGE (phapdien)-[:DERIVED_FROM]->(article)
"""


@dataclass(frozen=True)
class GraphIndexBuildSummary:
    """Summary returned after building the graph index."""

    mode: str
    legal_article_rows: int
    legal_article_batches: int
    phapdien_mapping_rows: int
    phapdien_mapping_batches: int
    constraints_created: int
    recreated: bool


def build_graph_index(
    legal_articles_path: str | Path | None = None,
    phapdien_mapping_path: str | Path | None = None,
    *,
    client: Neo4jClient | None = None,
    mode: str = "upsert",
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_rows: int | None = None,
) -> GraphIndexBuildSummary:
    """Build Neo4j Law/Article/PhapdienArticle graph index.

    Args:
        legal_articles_path: Optional path to canonical legal articles parquet.
        phapdien_mapping_path: Optional path to phapdien-to-VBPL mapping parquet.
        client: Optional Neo4jClient, useful for tests and dependency injection.
        mode: ``upsert`` by default; ``recreate`` deletes managed graph labels first.
        batch_size: Number of rows per Neo4j transaction.
        max_rows: Optional sample limit for smoke tests.
    """

    _validate_mode(mode)
    _validate_batch_size(batch_size)
    _validate_max_rows(max_rows)

    settings = get_settings()
    processed_dir = settings.paths.processed_dir
    article_path = Path(legal_articles_path) if legal_articles_path else processed_dir / "legal_articles.parquet"
    mapping_path = (
        Path(phapdien_mapping_path)
        if phapdien_mapping_path
        else processed_dir / "phapdien_to_vbpl_map.parquet"
    )
    graph_client = client or Neo4jClient()

    _run_constraints(graph_client)
    recreated = False
    if mode == "recreate":
        graph_client.run_write_query(RECREATE_QUERY)
        recreated = True

    legal_rows = _load_legal_article_rows(article_path, max_rows=max_rows)
    legal_batches = _write_article_batches(graph_client, legal_rows, batch_size=batch_size)

    mapping_rows: list[dict[str, Any]] = []
    mapping_batches = 0
    if mapping_path.exists():
        mapping_rows = _load_phapdien_mapping_rows(mapping_path, max_rows=max_rows)
        mapping_batches = _write_phapdien_mapping_batches(
            graph_client,
            mapping_rows,
            batch_size=batch_size,
        )
    else:
        logger.info("Skipping Phapdien graph mapping because file does not exist: %s", mapping_path)

    summary = GraphIndexBuildSummary(
        mode=mode,
        legal_article_rows=len(legal_rows),
        legal_article_batches=legal_batches,
        phapdien_mapping_rows=len(mapping_rows),
        phapdien_mapping_batches=mapping_batches,
        constraints_created=len(CONSTRAINT_QUERIES),
        recreated=recreated,
    )
    logger.info("Built Neo4j graph index: %s", summary)
    return summary


def _run_constraints(client: Neo4jClient) -> None:
    for query in CONSTRAINT_QUERIES:
        client.run_write_query(query)


def _write_article_batches(
    client: Neo4jClient,
    rows: list[dict[str, Any]],
    *,
    batch_size: int,
) -> int:
    batches = 0
    for batch in _iter_batches(rows, batch_size):
        client.run_write_query(UPSERT_ARTICLE_GRAPH_QUERY, {"rows": batch})
        batches += 1
    return batches


def _write_phapdien_mapping_batches(
    client: Neo4jClient,
    rows: list[dict[str, Any]],
    *,
    batch_size: int,
) -> int:
    batches = 0
    for batch in _iter_batches(rows, batch_size):
        client.run_write_query(UPSERT_PHAPDIEN_MAPPING_QUERY, {"rows": batch})
        batches += 1
    return batches


def _load_legal_article_rows(path: Path, *, max_rows: int | None) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Legal articles parquet not found: {path}")

    df = pl.read_parquet(path)
    _validate_columns(df, LEGAL_ARTICLE_COLUMNS, source_name="legal_articles")
    if max_rows is not None:
        df = df.head(max_rows)

    rows: list[dict[str, Any]] = []
    skipped = 0
    for row in df.select(LEGAL_ARTICLE_COLUMNS).iter_rows(named=True):
        normalized = _normalize_legal_article_row(row)
        if normalized is None:
            skipped += 1
            continue
        rows.append(normalized)

    if skipped:
        logger.warning("Skipped invalid legal article rows for graph index: count=%s", skipped)
    return rows


def _load_phapdien_mapping_rows(path: Path, *, max_rows: int | None) -> list[dict[str, Any]]:
    df = pl.read_parquet(path)
    _validate_columns(df, PHAPDIEN_MAPPING_COLUMNS, source_name="phapdien_to_vbpl_map")
    if max_rows is not None:
        df = df.head(max_rows)

    rows: list[dict[str, Any]] = []
    skipped = 0
    for row in df.select(PHAPDIEN_MAPPING_COLUMNS).iter_rows(named=True):
        normalized = _normalize_phapdien_mapping_row(row)
        if normalized is None:
            skipped += 1
            continue
        rows.append(normalized)

    if skipped:
        logger.warning("Skipped invalid phapdien mapping rows for graph index: count=%s", skipped)
    return rows


def _normalize_legal_article_row(row: dict[str, Any]) -> dict[str, Any] | None:
    article_id = normalize_vietnamese_text(row.get("article_id"))
    law_id = normalize_vietnamese_text(row.get("law_id"))
    law_title = normalize_vietnamese_text(row.get("law_title"))
    article_no = normalize_article_no(row.get("article_no"))
    if not article_id or not law_id or not law_title or not article_no:
        return None

    return {
        "article_id": article_id,
        "law_id": law_id,
        "law_title": law_title,
        "article_no": article_no,
        "article_title": normalize_vietnamese_text(row.get("article_title")),
        "source_url": normalize_vietnamese_text(row.get("source_url")),
        "domain": normalize_vietnamese_text(row.get("domain")),
        "status": normalize_vietnamese_text(row.get("status")),
    }


def _normalize_phapdien_mapping_row(row: dict[str, Any]) -> dict[str, Any] | None:
    phapdien_id = normalize_vietnamese_text(row.get("phapdien_id"))
    legal_article_id = normalize_vietnamese_text(row.get("legal_article_id"))
    if not phapdien_id or not legal_article_id:
        return None

    return {
        "phapdien_id": phapdien_id,
        "legal_article_id": legal_article_id,
        "law_id": normalize_vietnamese_text(row.get("law_id")),
        "law_title": normalize_vietnamese_text(row.get("law_title")),
        "article_no": normalize_article_no(row.get("article_no")),
        "mapping_score": _to_float(row.get("mapping_score")),
        "mapping_method": normalize_vietnamese_text(row.get("mapping_method")),
    }


def _validate_columns(df: pl.DataFrame, required_columns: list[str], *, source_name: str) -> None:
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns for {source_name}: {missing_columns}")


def _validate_mode(mode: str) -> None:
    if mode not in VALID_BUILD_MODES:
        raise ValueError(f"Graph index mode must be one of {sorted(VALID_BUILD_MODES)}: {mode}")


def _validate_batch_size(batch_size: int) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")


def _validate_max_rows(max_rows: int | None) -> None:
    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be a positive integer when provided")


def _iter_batches(rows: list[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)

