"""DuckDB helper for local parquet-backed data access."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DuckDBClient:
    """Small DuckDB wrapper for querying processed parquet files."""

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self.database_path = str(database_path)
        self._connection: Any | None = None

    @property
    def connection(self) -> Any:
        """Return a lazily created DuckDB connection."""

        if self._connection is None:
            try:
                import duckdb
            except ImportError as exc:
                raise RuntimeError("Missing dependency: duckdb") from exc

            self._connection = duckdb.connect(self.database_path)

        return self._connection

    def read_parquet(self, parquet_path: str | Path, *, table_name: str | None = None) -> Any:
        """Read a parquet file with DuckDB and return a relation.

        Args:
            parquet_path: Path to a parquet file.
            table_name: Optional temporary view name for repeated queries.

        Raises:
            FileNotFoundError: If the parquet path does not exist.
        """

        path = Path(parquet_path)
        if not path.exists():
            raise FileNotFoundError(f"Parquet file not found: {path}")

        relation = self.connection.read_parquet(str(path))
        if table_name:
            # Tạo view tạm giúp các bước indexing truy vấn lại parquet bằng SQL rõ ràng.
            relation.create_view(table_name, replace=True)

        return relation

    def execute(self, query: str, parameters: object | None = None) -> Any:
        """Execute a SQL query using the underlying DuckDB connection."""

        if parameters is None:
            return self.connection.execute(query)
        return self.connection.execute(query, parameters)

    def close(self) -> None:
        """Close the DuckDB connection if it has been opened."""

        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def health_check(self) -> bool:
        """Return True when DuckDB can execute a trivial query."""

        try:
            self.connection.execute("SELECT 1").fetchone()
            return True
        except Exception:
            logger.exception("DuckDB health check failed")
            return False

    def __enter__(self) -> "DuckDBClient":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()
