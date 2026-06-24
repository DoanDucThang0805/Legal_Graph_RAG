"""Neo4j graph expansion utility for canonical article candidates."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.infrastructure.graph_store.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

DEFAULT_MAX_NEIGHBORS = 20
DEFAULT_SCORE_CAP = 0.05
DEFAULT_ALLOWED_RELATION_TYPES = ("HAS_ARTICLE", "RELATED_TO", "REFERENCES", "DERIVED_FROM")

GRAPH_EXPANSION_QUERY = """
MATCH (seed:Article)
WHERE seed.article_id IN $seed_article_ids
CALL {
    WITH seed
    MATCH (law:Law)-[:HAS_ARTICLE]->(seed)
    MATCH (law)-[:HAS_ARTICLE]->(neighbor:Article)
    WHERE neighbor.article_id <> seed.article_id
      AND 'HAS_ARTICLE' IN $allow_relation_types
    RETURN
        neighbor.article_id AS article_id,
        'HAS_ARTICLE' AS relation_type,
        seed.article_id AS seed_article_id,
        0.02 AS score

    UNION ALL

    WITH seed
    MATCH (seed)-[relation:RELATED_TO|REFERENCES]-(neighbor:Article)
    WHERE type(relation) IN $allow_relation_types
    RETURN
        neighbor.article_id AS article_id,
        type(relation) AS relation_type,
        seed.article_id AS seed_article_id,
        CASE type(relation)
            WHEN 'RELATED_TO' THEN 0.04
            WHEN 'REFERENCES' THEN 0.03
            ELSE 0.01
        END AS score

    UNION ALL

    WITH seed
    MATCH (phapdien:PhapdienArticle)-[:DERIVED_FROM]->(seed)
    MATCH (phapdien)-[:DERIVED_FROM]->(neighbor:Article)
    WHERE neighbor.article_id <> seed.article_id
      AND 'DERIVED_FROM' IN $allow_relation_types
    RETURN
        neighbor.article_id AS article_id,
        'DERIVED_FROM' AS relation_type,
        seed.article_id AS seed_article_id,
        0.015 AS score
}
RETURN
    article_id,
    relation_type,
    seed_article_id,
    score
ORDER BY score DESC, article_id ASC
LIMIT $limit
"""


@dataclass(frozen=True)
class GraphExpansionResult:
    """Structured result returned by GraphExpander."""

    neighbor_article_ids: list[str] = field(default_factory=list)
    graph_boost_scores: dict[str, float] = field(default_factory=dict)
    debug_sources: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "neighbor_article_ids": self.neighbor_article_ids,
            "graph_boost_scores": self.graph_boost_scores,
            "debug_sources": self.debug_sources,
            "status": self.status,
        }


class GraphExpander:
    """Suggest soft graph neighbors for already retrieved article candidates."""

    def __init__(
        self,
        *,
        client: Neo4jClient | None = None,
        enabled: bool = False,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
        score_cap: float = DEFAULT_SCORE_CAP,
        allow_relation_types: list[str] | tuple[str, ...] | None = None,
        min_seed_count: int = 1,
    ) -> None:
        _validate_positive_int(max_neighbors, "max_neighbors")
        _validate_positive_float(score_cap, "score_cap")
        _validate_positive_int(min_seed_count, "min_seed_count")

        self.client = client
        self.enabled = enabled
        self.max_neighbors = max_neighbors
        self.score_cap = score_cap
        self.allow_relation_types = tuple(allow_relation_types or DEFAULT_ALLOWED_RELATION_TYPES)
        self.min_seed_count = min_seed_count

    def expand(self, candidates: list[Any]) -> GraphExpansionResult:
        """Return graph neighbor suggestions without mutating retrieval candidates."""

        seed_article_ids = _extract_unique_article_ids(candidates)
        if not self.enabled:
            return GraphExpansionResult(status="disabled")
        if not seed_article_ids:
            return GraphExpansionResult(status="ok")
        if len(seed_article_ids) < self.min_seed_count:
            return GraphExpansionResult(status="ok")

        try:
            rows = self._client.run_read_query(
                GRAPH_EXPANSION_QUERY,
                {
                    "seed_article_ids": seed_article_ids,
                    "allow_relation_types": list(self.allow_relation_types),
                    "limit": self.max_neighbors * max(len(seed_article_ids), 1),
                },
            )
        except Exception:
            logger.exception("Graph expansion failed")
            return GraphExpansionResult(status="runtime_error")

        return _build_expansion_result(
            rows,
            seed_article_ids=set(seed_article_ids),
            max_neighbors=self.max_neighbors,
            score_cap=self.score_cap,
        )

    @property
    def _client(self) -> Neo4jClient:
        """Return injected client or construct a lazy Neo4jClient only when expanding."""

        if self.client is None:
            self.client = Neo4jClient()
        return self.client


def _build_expansion_result(
    rows: list[dict[str, Any]],
    *,
    seed_article_ids: set[str],
    max_neighbors: int,
    score_cap: float,
) -> GraphExpansionResult:
    scores: dict[str, float] = {}
    debug_by_article: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        article_id = str(row.get("article_id") or "").strip()
        if not article_id or article_id in seed_article_ids:
            continue

        raw_score = _to_float(row.get("score"))
        score = min(raw_score, score_cap)
        current_score = scores.get(article_id, 0.0)
        scores[article_id] = min(current_score + score, score_cap)
        debug_by_article.setdefault(article_id, []).append(
            {
                "article_id": article_id,
                "seed_article_id": str(row.get("seed_article_id") or "").strip(),
                "relation_type": str(row.get("relation_type") or "").strip(),
                "score": score,
            }
        )

    ranked_article_ids = sorted(scores, key=lambda article_id: (-scores[article_id], article_id))
    limited_article_ids = ranked_article_ids[:max_neighbors]
    limited_scores = {article_id: scores[article_id] for article_id in limited_article_ids}
    debug_sources = [
        source
        for article_id in limited_article_ids
        for source in debug_by_article.get(article_id, [])
    ]
    return GraphExpansionResult(
        neighbor_article_ids=limited_article_ids,
        graph_boost_scores=limited_scores,
        debug_sources=debug_sources,
        status="ok",
    )


def _extract_unique_article_ids(candidates: list[Any]) -> list[str]:
    article_ids: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        article_id = _extract_article_id(candidate)
        if article_id and article_id not in seen:
            article_ids.append(article_id)
            seen.add(article_id)
    return article_ids


def _extract_article_id(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate.strip()
    if isinstance(candidate, dict):
        return str(candidate.get("article_id") or "").strip()
    return str(getattr(candidate, "article_id", "") or "").strip()


def _validate_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _validate_positive_float(value: float, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0

