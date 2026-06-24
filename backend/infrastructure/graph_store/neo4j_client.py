"""Thin Neo4j client wrapper for Phase 8 graph expansion.

This module does not connect to Neo4j at import time or construction time.
The official Neo4j driver is imported lazily only when a query or health
check needs a live driver.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Neo4jClientConfig:
    """Connection settings for a local or remote Neo4j service."""

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str | None = None
    database: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Neo4jClientConfig":
        """Build config from environment variables with local defaults."""

        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD") or None,
            database=os.getenv("NEO4J_DATABASE") or None,
            timeout_seconds=float(os.getenv("NEO4J_TIMEOUT_SECONDS", "10")),
        )


class Neo4jClient:
    """Lazy Neo4j driver wrapper used by graph indexing and expansion code."""

    def __init__(
        self,
        config: Neo4jClientConfig | None = None,
        driver: Any | None = None,
    ) -> None:
        self.config = config or Neo4jClientConfig.from_env()
        self._driver = driver

    @property
    def driver(self) -> Any:
        """Return a lazily constructed Neo4j driver."""

        if self._driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:
                raise RuntimeError("Missing dependency: neo4j") from exc

            auth = None
            if self.config.password is not None:
                auth = (self.config.username, self.config.password)

            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=auth,
                connection_timeout=self.config.timeout_seconds,
            )

        return self._driver

    def close(self) -> None:
        """Close the underlying driver if it has been created."""

        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def health_check(self) -> bool:
        """Return True when Neo4j responds to a lightweight read query."""

        try:
            self.run_read_query("RETURN 1 AS ok")
            return True
        except Exception:
            logger.exception("Neo4j health check failed")
            return False

    def run_read_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a read query and return records as dictionaries."""

        return self._run_query(query, parameters, database, is_write=False)

    def run_write_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a write query and return records as dictionaries."""

        return self._run_query(query, parameters, database, is_write=True)

    def _run_query(
        self,
        query: str,
        parameters: dict[str, Any] | None,
        database: str | None,
        *,
        is_write: bool,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query through a managed Neo4j session."""

        session_kwargs = self._build_session_kwargs(database)
        with self.driver.session(**session_kwargs) as session:
            method = self._get_transaction_method(session, is_write=is_write)
            return method(self._execute_transaction, query, parameters or {})

    def _build_session_kwargs(self, database: str | None) -> dict[str, Any]:
        """Build session kwargs without passing database=None to the driver."""

        session_database = database if database is not None else self.config.database
        if not session_database:
            return {}
        return {"database": session_database}

    @staticmethod
    def _get_transaction_method(session: Any, *, is_write: bool) -> Callable[..., Any]:
        """Return transaction runner compatible with Neo4j driver v4/v5."""

        if is_write:
            method = getattr(session, "execute_write", None)
            if method is not None:
                return method
            return session.write_transaction

        method = getattr(session, "execute_read", None)
        if method is not None:
            return method
        return session.read_transaction

    @staticmethod
    def _execute_transaction(
        transaction: Any,
        query: str,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Run Cypher inside an existing transaction and materialize records."""

        result = transaction.run(query, parameters)
        return [dict(record) for record in result]


