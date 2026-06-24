from __future__ import annotations

import builtins
import importlib
import sys
import types
from typing import Any

import pytest

from backend.infrastructure.graph_store.neo4j_client import Neo4jClient, Neo4jClientConfig


class FakeRecord(dict):
    pass


class FakeTransaction:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, query: str, parameters: dict[str, Any]) -> list[FakeRecord]:
        self.calls.append((query, parameters))
        return [FakeRecord(record) for record in self.records]


class FakeSession:
    def __init__(self, transaction: FakeTransaction) -> None:
        self.transaction = transaction
        self.read_calls = 0
        self.write_calls = 0

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute_read(self, callback: Any, query: str, parameters: dict[str, Any]) -> Any:
        self.read_calls += 1
        return callback(self.transaction, query, parameters)

    def execute_write(self, callback: Any, query: str, parameters: dict[str, Any]) -> Any:
        self.write_calls += 1
        return callback(self.transaction, query, parameters)


class FakeDriver:
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.transaction = FakeTransaction(records or [{"value": 1}])
        self.session_kwargs: list[dict[str, Any]] = []
        self.sessions: list[FakeSession] = []
        self.closed = False

    def session(self, **kwargs: Any) -> FakeSession:
        self.session_kwargs.append(kwargs)
        session = FakeSession(self.transaction)
        self.sessions.append(session)
        return session

    def close(self) -> None:
        self.closed = True


def test_module_import_does_not_require_neo4j_driver() -> None:
    module = importlib.import_module("backend.infrastructure.graph_store.neo4j_client")

    assert module.Neo4jClient is Neo4jClient


def test_constructor_does_not_create_driver() -> None:
    client = Neo4jClient(config=Neo4jClientConfig(password="secret"))

    assert client._driver is None


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_URI", "bolt://graph.local:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j_user")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "legal_graph")
    monkeypatch.setenv("NEO4J_TIMEOUT_SECONDS", "4.5")

    config = Neo4jClientConfig.from_env()

    assert config == Neo4jClientConfig(
        uri="bolt://graph.local:7687",
        username="neo4j_user",
        password="secret",
        database="legal_graph",
        timeout_seconds=4.5,
    )


def test_missing_driver_raises_clear_error_when_query_is_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "neo4j":
            raise ImportError("No module named neo4j")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = Neo4jClient(config=Neo4jClientConfig(password="secret"))

    with pytest.raises(RuntimeError, match="Missing dependency: neo4j"):
        client.run_read_query("RETURN 1")


def test_health_check_returns_false_when_driver_dependency_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "neo4j":
            raise ImportError("No module named neo4j")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = Neo4jClient(config=Neo4jClientConfig(password="secret"))

    assert client.health_check() is False


def test_driver_is_lazy_created_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    fake_driver = FakeDriver()

    class FakeGraphDatabase:
        @staticmethod
        def driver(uri: str, **kwargs: Any) -> FakeDriver:
            calls.append({"uri": uri, **kwargs})
            return fake_driver

    monkeypatch.setitem(
        sys.modules,
        "neo4j",
        types.SimpleNamespace(GraphDatabase=FakeGraphDatabase),
    )
    config = Neo4jClientConfig(
        uri="bolt://neo4j.example:7687",
        username="user",
        password="secret",
        timeout_seconds=3.5,
    )
    client = Neo4jClient(config=config)

    rows = client.run_read_query("RETURN $value AS value", {"value": 42})

    assert rows == [{"value": 1}]
    assert calls == [
        {
            "uri": "bolt://neo4j.example:7687",
            "auth": ("user", "secret"),
            "connection_timeout": 3.5,
        }
    ]


def test_run_read_query_returns_list_of_dicts_and_uses_database() -> None:
    fake_driver = FakeDriver(records=[{"article_id": "a1"}, {"article_id": "a2"}])
    client = Neo4jClient(
        config=Neo4jClientConfig(password="secret", database="neo4j"),
        driver=fake_driver,
    )

    rows = client.run_read_query("MATCH (a) RETURN a.article_id AS article_id")

    assert rows == [{"article_id": "a1"}, {"article_id": "a2"}]
    assert fake_driver.session_kwargs == [{"database": "neo4j"}]
    assert fake_driver.sessions[0].read_calls == 1
    assert fake_driver.sessions[0].write_calls == 0


def test_run_write_query_returns_list_of_dicts_and_allows_database_override() -> None:
    fake_driver = FakeDriver(records=[{"created": 1}])
    client = Neo4jClient(
        config=Neo4jClientConfig(password="secret", database="default_db"),
        driver=fake_driver,
    )

    rows = client.run_write_query(
        "CREATE (n:Node {id: $id}) RETURN 1 AS created",
        {"id": "n1"},
        database="override_db",
    )

    assert rows == [{"created": 1}]
    assert fake_driver.session_kwargs == [{"database": "override_db"}]
    assert fake_driver.sessions[0].read_calls == 0
    assert fake_driver.sessions[0].write_calls == 1


def test_health_check_returns_true_when_query_succeeds() -> None:
    client = Neo4jClient(
        config=Neo4jClientConfig(password="secret"),
        driver=FakeDriver(records=[{"ok": 1}]),
    )

    assert client.health_check() is True


def test_health_check_returns_false_on_connection_error() -> None:
    class FailingDriver:
        def session(self, **_kwargs: Any) -> Any:
            raise ConnectionError("Neo4j is unavailable")

    client = Neo4jClient(
        config=Neo4jClientConfig(password="secret"),
        driver=FailingDriver(),
    )

    assert client.health_check() is False


def test_close_closes_existing_driver_and_clears_reference() -> None:
    fake_driver = FakeDriver()
    client = Neo4jClient(config=Neo4jClientConfig(password="secret"), driver=fake_driver)

    client.close()

    assert fake_driver.closed is True
    assert client._driver is None

