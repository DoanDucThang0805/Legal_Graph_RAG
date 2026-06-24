from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.retrieval.graph_expander import GRAPH_EXPANSION_QUERY, GraphExpander


class FakeNeo4jClient:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        *,
        should_fail: bool = False,
    ) -> None:
        self.rows = rows or []
        self.should_fail = should_fail
        self.read_calls: list[tuple[str, dict[str, Any] | None]] = []

    def run_read_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        self.read_calls.append((query, parameters))
        if self.should_fail:
            raise ConnectionError("Neo4j unavailable")
        return self.rows


@dataclass
class CandidateObject:
    article_id: str


def test_module_import() -> None:
    from backend.retrieval.graph_expander import GraphExpander as ImportedGraphExpander

    assert ImportedGraphExpander is GraphExpander


def test_disabled_mode_returns_empty_without_calling_client() -> None:
    client = FakeNeo4jClient(rows=[{"article_id": "neighbor"}])
    expander = GraphExpander(client=client, enabled=False)

    result = expander.expand(["seed-1"])

    assert result.to_dict() == {
        "neighbor_article_ids": [],
        "graph_boost_scores": {},
        "debug_sources": [],
        "status": "disabled",
    }
    assert client.read_calls == []


def test_empty_input_returns_ok_without_calling_client() -> None:
    client = FakeNeo4jClient()
    expander = GraphExpander(client=client, enabled=True)

    result = expander.expand([])

    assert result.status == "ok"
    assert result.neighbor_article_ids == []
    assert result.graph_boost_scores == {}
    assert client.read_calls == []


def test_expand_calls_run_read_query_when_enabled() -> None:
    client = FakeNeo4jClient(rows=[{"article_id": "neighbor-1", "score": 0.02}])
    expander = GraphExpander(
        client=client,
        enabled=True,
        max_neighbors=5,
        allow_relation_types=("HAS_ARTICLE",),
    )

    result = expander.expand(["seed-1"])

    assert result.status == "ok"
    assert result.neighbor_article_ids == ["neighbor-1"]
    assert len(client.read_calls) == 1
    query, parameters = client.read_calls[0]
    assert query == GRAPH_EXPANSION_QUERY
    assert parameters == {
        "seed_article_ids": ["seed-1"],
        "allow_relation_types": ["HAS_ARTICLE"],
        "limit": 5,
    }
    assert "seed-1" not in query


def test_expand_deduplicates_neighbors_and_caps_score() -> None:
    client = FakeNeo4jClient(
        rows=[
            {
                "article_id": "neighbor-1",
                "seed_article_id": "seed-1",
                "relation_type": "RELATED_TO",
                "score": 0.04,
            },
            {
                "article_id": "neighbor-1",
                "seed_article_id": "seed-2",
                "relation_type": "HAS_ARTICLE",
                "score": 0.04,
            },
            {
                "article_id": "neighbor-2",
                "seed_article_id": "seed-1",
                "relation_type": "HAS_ARTICLE",
                "score": 0.02,
            },
        ]
    )
    expander = GraphExpander(client=client, enabled=True, score_cap=0.05)

    result = expander.expand(["seed-1", "seed-2"])

    assert result.neighbor_article_ids == ["neighbor-1", "neighbor-2"]
    assert result.graph_boost_scores == {"neighbor-1": 0.05, "neighbor-2": 0.02}
    assert len(result.debug_sources) == 3


def test_expand_removes_seed_article_ids_from_neighbors() -> None:
    client = FakeNeo4jClient(
        rows=[
            {"article_id": "seed-1", "seed_article_id": "seed-2", "score": 0.04},
            {"article_id": "neighbor-1", "seed_article_id": "seed-1", "score": 0.03},
        ]
    )
    expander = GraphExpander(client=client, enabled=True)

    result = expander.expand(["seed-1", "seed-2"])

    assert result.neighbor_article_ids == ["neighbor-1"]
    assert "seed-1" not in result.graph_boost_scores


def test_expand_applies_max_neighbors() -> None:
    client = FakeNeo4jClient(
        rows=[
            {"article_id": "neighbor-1", "score": 0.01},
            {"article_id": "neighbor-2", "score": 0.04},
            {"article_id": "neighbor-3", "score": 0.03},
        ]
    )
    expander = GraphExpander(client=client, enabled=True, max_neighbors=2)

    result = expander.expand(["seed-1"])

    assert result.neighbor_article_ids == ["neighbor-2", "neighbor-3"]
    assert set(result.graph_boost_scores) == {"neighbor-2", "neighbor-3"}


def test_runtime_error_returns_empty_fallback() -> None:
    client = FakeNeo4jClient(should_fail=True)
    expander = GraphExpander(client=client, enabled=True)

    result = expander.expand(["seed-1"])

    assert result.status == "runtime_error"
    assert result.neighbor_article_ids == []
    assert result.graph_boost_scores == {}
    assert len(client.read_calls) == 1


def test_expand_accepts_dict_and_object_candidates() -> None:
    client = FakeNeo4jClient(rows=[{"article_id": "neighbor-1", "score": 0.02}])
    expander = GraphExpander(client=client, enabled=True)

    result = expander.expand(
        [
            {"article_id": "seed-1"},
            CandidateObject(article_id="seed-2"),
            {"article_id": "seed-1"},
        ]
    )

    assert result.neighbor_article_ids == ["neighbor-1"]
    assert client.read_calls[0][1]["seed_article_ids"] == ["seed-1", "seed-2"]


def test_min_seed_count_returns_ok_without_calling_client() -> None:
    client = FakeNeo4jClient()
    expander = GraphExpander(client=client, enabled=True, min_seed_count=2)

    result = expander.expand(["seed-1"])

    assert result.status == "ok"
    assert result.neighbor_article_ids == []
    assert client.read_calls == []

