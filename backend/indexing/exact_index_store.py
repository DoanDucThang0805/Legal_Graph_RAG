"""DuckDB-backed exact index for runtime lookup.

Module này tối ưu phần runtime của exact index: thay vì load một file JSON
~2GB vào RAM, dữ liệu được lưu trong DuckDB và query theo khóa cần dùng.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from backend.indexing.build_exact_index import (
    extract_accounting_accounts,
    extract_deadline_numbers,
    extract_sanction_terms,
)

logger = logging.getLogger(__name__)


EXACT_INDEX_TABLES: tuple[str, ...] = (
    "exact_metadata",
    "exact_articles",
    "exact_by_law_id",
    "exact_by_article_no",
    "exact_by_law_article",
    "exact_accounting_accounts",
    "exact_deadline_numbers",
    "exact_sanction_terms",
)


@dataclass(frozen=True)
class ExactArticleRecord:
    """Canonical article record returned from exact lookup."""

    article_id: str
    law_id: str
    law_title: str
    article_no: str
    article_title: str
    source_url: str
    domain: str
    status: str


class ExactIndexStore:
    """Runtime reader for DuckDB exact index."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def get_metadata(self) -> dict[str, Any]:
        conn = _connect_readonly(self.db_path)
        try:
            rows = conn.execute("SELECT key, value_json FROM exact_metadata").fetchall()
        finally:
            conn.close()
        return {key: json.loads(value_json) for key, value_json in rows}

    def get_article(self, article_id: str) -> ExactArticleRecord | None:
        rows = self.get_articles_by_ids([article_id])
        return rows[0] if rows else None

    def get_articles_by_ids(self, article_ids: Iterable[str]) -> list[ExactArticleRecord]:
        ids = _unique_non_empty(article_ids)
        if not ids:
            return []

        conn = _connect_readonly(self.db_path)
        try:
            placeholders = ", ".join("?" for _ in ids)
            rows = conn.execute(
                f"""
                SELECT
                    article_id,
                    law_id,
                    law_title,
                    article_no,
                    article_title,
                    source_url,
                    domain,
                    status
                FROM exact_articles
                WHERE article_id IN ({placeholders})
                ORDER BY article_id
                """,
                ids,
            ).fetchall()
        finally:
            conn.close()

        return [_article_record_from_row(row) for row in rows]

    def find_by_law_id(self, law_id: str, *, limit: int = 100) -> list[str]:
        return self._lookup_article_ids("exact_by_law_id", "law_id", law_id, limit=limit)

    def find_by_article_no(self, article_no: str, *, limit: int = 100) -> list[str]:
        return self._lookup_article_ids("exact_by_article_no", "article_no", article_no, limit=limit)

    def find_by_law_article(self, law_id: str, article_no: str, *, limit: int = 100) -> list[str]:
        if not law_id or not article_no:
            return []

        conn = _connect_readonly(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT article_id
                FROM exact_by_law_article
                WHERE law_id = ? AND article_no = ?
                ORDER BY article_id
                LIMIT ?
                """,
                [law_id, article_no, limit],
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def find_by_accounting_account(self, account: str, *, limit: int = 100) -> list[str]:
        return self._lookup_article_ids("exact_accounting_accounts", "account", account, limit=limit)

    def find_by_deadline(self, deadline: str, *, limit: int = 100) -> list[str]:
        return self._lookup_article_ids("exact_deadline_numbers", "deadline", deadline, limit=limit)

    def find_by_sanction_term(self, term: str, *, limit: int = 100) -> list[str]:
        return self._lookup_article_ids("exact_sanction_terms", "term", term, limit=limit)

    def _lookup_article_ids(self, table: str, key_column: str, key: str, *, limit: int) -> list[str]:
        if not key:
            return []
        if table not in EXACT_INDEX_TABLES:
            raise ValueError(f"Unsupported exact index table: {table}")

        conn = _connect_readonly(self.db_path)
        try:
            rows = conn.execute(
                f"""
                SELECT article_id
                FROM {table}
                WHERE {key_column} = ?
                ORDER BY article_id
                LIMIT ?
                """,
                [key, limit],
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]


def build_exact_duckdb_index(
    source_parquet_path: str | Path,
    output_db_path: str | Path,
    *,
    recreate: bool = True,
) -> dict[str, Any]:
    """Build DuckDB exact index from canonical legal_articles parquet.

    Exact index này vẫn chỉ dùng article-level canonical corpus. Các bảng lookup
    trả về `article_id`; không sinh citation từ chunk/phapdien/anle.
    """

    source_path = Path(source_parquet_path)
    output_path = Path(output_db_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Exact index source parquet not found: {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if recreate and output_path.exists():
        output_path.unlink()

    logger.info("Building DuckDB exact index from %s to %s", source_path, output_path)
    conn = duckdb.connect(str(output_path))
    try:
        _create_schema(conn)
        _load_articles(conn, source_path)
        article_count = conn.execute("SELECT COUNT(*) FROM exact_articles").fetchone()[0]
        _load_direct_lookup_tables(conn)
        _load_feature_lookup_tables(conn)
        _write_metadata(conn, source_path, article_count)
        _create_indexes(conn)
    finally:
        conn.close()

    logger.info("Built DuckDB exact index with %s articles", article_count)
    return {
        "output_path": str(output_path),
        "article_count": article_count,
        "tables": list(EXACT_INDEX_TABLES),
    }


def _create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    for table in EXACT_INDEX_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    conn.execute("CREATE TABLE exact_metadata(key VARCHAR PRIMARY KEY, value_json VARCHAR)")
    conn.execute(
        """
        CREATE TABLE exact_articles(
            article_id VARCHAR PRIMARY KEY,
            law_id VARCHAR,
            law_title VARCHAR,
            article_no VARCHAR,
            article_title VARCHAR,
            content VARCHAR,
            source_url VARCHAR,
            domain VARCHAR,
            status VARCHAR
        )
        """
    )
    conn.execute("CREATE TABLE exact_by_law_id(law_id VARCHAR, article_id VARCHAR)")
    conn.execute("CREATE TABLE exact_by_article_no(article_no VARCHAR, article_id VARCHAR)")
    conn.execute("CREATE TABLE exact_by_law_article(law_id VARCHAR, article_no VARCHAR, article_id VARCHAR)")
    conn.execute("CREATE TABLE exact_accounting_accounts(account VARCHAR, article_id VARCHAR)")
    conn.execute("CREATE TABLE exact_deadline_numbers(deadline VARCHAR, article_id VARCHAR)")
    conn.execute("CREATE TABLE exact_sanction_terms(term VARCHAR, article_id VARCHAR)")


def _load_articles(conn: duckdb.DuckDBPyConnection, source_path: Path) -> None:
    columns = _get_parquet_columns(conn, source_path)
    article_id_expr = _required_column_expr(columns, "article_id")
    content_expr = _first_existing_column_expr(
        columns,
        ("content", "article_text", "article_content", "text", "full_text", "normalized_text", "clean_text"),
    )
    conn.execute(
        f"""
        INSERT INTO exact_articles
        SELECT
            CAST({article_id_expr} AS VARCHAR) AS article_id,
            {_optional_column_expr(columns, "law_id")} AS law_id,
            {_optional_column_expr(columns, "law_title")} AS law_title,
            {_optional_column_expr(columns, "article_no")} AS article_no,
            {_optional_column_expr(columns, "article_title")} AS article_title,
            {content_expr} AS content,
            {_optional_column_expr(columns, "source_url")} AS source_url,
            {_optional_column_expr(columns, "domain")} AS domain,
            {_optional_column_expr(columns, "status")} AS status
        FROM read_parquet(?) AS src
        WHERE {article_id_expr} IS NOT NULL AND CAST({article_id_expr} AS VARCHAR) != ''
        """,
        [str(source_path)],
    )


def _load_direct_lookup_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        INSERT INTO exact_by_law_id
        SELECT law_id, article_id FROM exact_articles WHERE law_id != ''
        """
    )
    conn.execute(
        """
        INSERT INTO exact_by_article_no
        SELECT article_no, article_id FROM exact_articles WHERE article_no != ''
        """
    )
    conn.execute(
        """
        INSERT INTO exact_by_law_article
        SELECT law_id, article_no, article_id
        FROM exact_articles
        WHERE law_id != '' AND article_no != ''
        """
    )


def _load_feature_lookup_tables(conn: duckdb.DuckDBPyConnection, *, batch_size: int = 10_000) -> None:
    # Feature extraction dùng regex Python hiện có để giữ behavior nhất quán
    # với JSON exact index, nhưng chỉ lưu inverted index nhỏ vào DuckDB.
    batches = conn.execute("SELECT article_id, content FROM exact_articles").to_arrow_reader(batch_size=batch_size)
    for batch in batches:
        article_ids = batch.column("article_id").to_pylist()
        contents = batch.column("content").to_pylist()

        account_rows: list[tuple[str, str]] = []
        deadline_rows: list[tuple[str, str]] = []
        sanction_rows: list[tuple[str, str]] = []

        for article_id, content in zip(article_ids, contents, strict=True):
            account_rows.extend((value, article_id) for value in extract_accounting_accounts(content))
            deadline_rows.extend((value, article_id) for value in extract_deadline_numbers(content))
            sanction_rows.extend((value, article_id) for value in extract_sanction_terms(content))

        if account_rows:
            conn.executemany("INSERT INTO exact_accounting_accounts VALUES (?, ?)", account_rows)
        if deadline_rows:
            conn.executemany("INSERT INTO exact_deadline_numbers VALUES (?, ?)", deadline_rows)
        if sanction_rows:
            conn.executemany("INSERT INTO exact_sanction_terms VALUES (?, ?)", sanction_rows)


def _get_parquet_columns(conn: duckdb.DuckDBPyConnection, source_path: Path) -> set[str]:
    rows = conn.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(source_path)]).fetchall()
    return {row[0] for row in rows}


def _required_column_expr(columns: set[str], column_name: str) -> str:
    if column_name not in columns:
        raise ValueError(f"Exact index source is missing required column: {column_name}")
    return f"src.{_quote_identifier(column_name)}"


def _optional_column_expr(columns: set[str], column_name: str) -> str:
    if column_name not in columns:
        logger.warning("Exact index source is missing optional column: %s", column_name)
        return "''"
    return f"COALESCE(CAST(src.{_quote_identifier(column_name)} AS VARCHAR), '')"


def _first_existing_column_expr(columns: set[str], candidates: tuple[str, ...]) -> str:
    for column_name in candidates:
        if column_name in columns:
            logger.info("Using %s as exact index content column", column_name)
            return f"COALESCE(CAST(src.{_quote_identifier(column_name)} AS VARCHAR), '')"
    raise ValueError(
        "Exact index source is missing a content column. "
        f"Tried: {', '.join(candidates)}"
    )


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _write_metadata(conn: duckdb.DuckDBPyConnection, source_path: Path, article_count: int) -> None:
    metadata = {
        "source_path": str(source_path),
        "article_count": article_count,
        "format": "duckdb",
        "canonical_source": "legal_articles",
    }
    rows = [(key, json.dumps(value, ensure_ascii=False)) for key, value in metadata.items()]
    conn.executemany("INSERT INTO exact_metadata VALUES (?, ?)", rows)


def _create_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_articles_article_id ON exact_articles(article_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_by_law_id ON exact_by_law_id(law_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_by_article_no ON exact_by_article_no(article_no)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_by_law_article ON exact_by_law_article(law_id, article_no)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_accounts ON exact_accounting_accounts(account)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_deadlines ON exact_deadline_numbers(deadline)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exact_sanctions ON exact_sanction_terms(term)")


def _connect_readonly(db_path: Path) -> duckdb.DuckDBPyConnection:
    if not db_path.exists():
        raise FileNotFoundError(f"Exact index DuckDB file not found: {db_path}")
    return duckdb.connect(str(db_path), read_only=True)


def _unique_non_empty(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _article_record_from_row(row: tuple[Any, ...]) -> ExactArticleRecord:
    return ExactArticleRecord(
        article_id=row[0],
        law_id=row[1],
        law_title=row[2],
        article_no=row[3],
        article_title=row[4],
        source_url=row[5],
        domain=row[6],
        status=row[7],
    )
