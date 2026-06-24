from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import pytest

from backend.indexing.build_graph_index import (
    CONSTRAINT_QUERIES,
    RECREATE_QUERY,
    UPSERT_ARTICLE_GRAPH_QUERY,
    UPSERT_PHAPDIEN_MAPPING_QUERY,
    build_graph_index,
)


class RecordingNeo4jClient:
    def __init__(self) -> None:
        self.write_calls: list[tuple[str, dict[str, Any] | None]] = []

    def run_write_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        self.write_calls.append((query, parameters))
        return []


def _legal_articles_df() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "article_id": "L1|Luật Test|Điều 1",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 01.",
                "article_title": "Quy định chung",
                "source_url": "https://example.test/1",
                "domain": "test",
                "status": "active",
            },
            {
                "article_id": "L1|Luật Test|Điều 2",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 2",
                "article_title": "Quy định riêng",
                "source_url": "https://example.test/2",
                "domain": "test",
                "status": "active",
            },
            {
                "article_id": "L2|Nghị định Test|Điều 3",
                "law_id": "L2",
                "law_title": "Nghị định Test",
                "article_no": "Điều 3",
                "article_title": "Xử phạt",
                "source_url": "https://example.test/3",
                "domain": "sanction",
                "status": "active",
            },
        ]
    )


def _mapping_df() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "phapdien_id": "pd-1",
                "legal_article_id": "L1|Luật Test|Điều 1",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 1",
                "mapping_score": 100.0,
                "mapping_method": "item_id_article_no",
            },
            {
                "phapdien_id": "pd-2",
                "legal_article_id": "L1|Luật Test|Điều 2",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 2",
                "mapping_score": 95.0,
                "mapping_method": "law_id_article_no",
            },
        ]
    )


def _write_inputs(tmp_path: Path, *, with_mapping: bool = True) -> tuple[Path, Path]:
    article_path = tmp_path / "legal_articles.parquet"
    mapping_path = tmp_path / "phapdien_to_vbpl_map.parquet"
    _legal_articles_df().write_parquet(article_path)
    if with_mapping:
        _mapping_df().write_parquet(mapping_path)
    return article_path, mapping_path


def test_module_import_does_not_build_graph() -> None:
    from backend.indexing import build_graph_index as module

    assert module.build_graph_index is build_graph_index


def test_build_graph_index_upsert_batches_articles_and_mappings(tmp_path: Path) -> None:
    article_path, mapping_path = _write_inputs(tmp_path)
    client = RecordingNeo4jClient()

    summary = build_graph_index(
        article_path,
        mapping_path,
        client=client,  # type: ignore[arg-type]
        batch_size=2,
    )

    assert summary.mode == "upsert"
    assert summary.legal_article_rows == 3
    assert summary.legal_article_batches == 2
    assert summary.phapdien_mapping_rows == 2
    assert summary.phapdien_mapping_batches == 1
    assert summary.constraints_created == len(CONSTRAINT_QUERIES)
    assert summary.recreated is False

    queries = [query for query, _params in client.write_calls]
    assert all("CREATE CONSTRAINT" in query and "IF NOT EXISTS" in query for query in queries[:3])
    assert queries.count(UPSERT_ARTICLE_GRAPH_QUERY) == 2
    assert queries.count(UPSERT_PHAPDIEN_MAPPING_QUERY) == 1

    first_article_params = client.write_calls[3][1]
    assert first_article_params == {
        "rows": [
            {
                "article_id": "L1|Luật Test|Điều 1",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 1",
                "article_title": "Quy định chung",
                "source_url": "https://example.test/1",
                "domain": "test",
                "status": "active",
            },
            {
                "article_id": "L1|Luật Test|Điều 2",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 2",
                "article_title": "Quy định riêng",
                "source_url": "https://example.test/2",
                "domain": "test",
                "status": "active",
            },
        ]
    }


def test_build_graph_index_recreate_runs_delete_after_constraints(tmp_path: Path) -> None:
    article_path, mapping_path = _write_inputs(tmp_path, with_mapping=False)
    client = RecordingNeo4jClient()

    summary = build_graph_index(
        article_path,
        mapping_path,
        client=client,  # type: ignore[arg-type]
        mode="recreate",
    )

    assert summary.recreated is True
    assert client.write_calls[3][0] == RECREATE_QUERY


def test_build_graph_index_max_rows_limits_smoke_data(tmp_path: Path) -> None:
    article_path, mapping_path = _write_inputs(tmp_path)
    client = RecordingNeo4jClient()

    summary = build_graph_index(
        article_path,
        mapping_path,
        client=client,  # type: ignore[arg-type]
        batch_size=10,
        max_rows=1,
    )

    assert summary.legal_article_rows == 1
    assert summary.phapdien_mapping_rows == 1
    article_batch = client.write_calls[3][1]
    mapping_batch = client.write_calls[4][1]
    assert article_batch is not None
    assert mapping_batch is not None
    assert len(article_batch["rows"]) == 1
    assert len(mapping_batch["rows"]) == 1


def test_build_graph_index_skips_missing_mapping_file(tmp_path: Path) -> None:
    article_path, mapping_path = _write_inputs(tmp_path, with_mapping=False)
    client = RecordingNeo4jClient()

    summary = build_graph_index(
        article_path,
        mapping_path,
        client=client,  # type: ignore[arg-type]
        batch_size=2,
    )

    assert summary.legal_article_rows == 3
    assert summary.phapdien_mapping_rows == 0
    assert summary.phapdien_mapping_batches == 0
    queries = [query for query, _params in client.write_calls]
    assert UPSERT_PHAPDIEN_MAPPING_QUERY not in queries


def test_build_graph_index_validates_options(tmp_path: Path) -> None:
    article_path, mapping_path = _write_inputs(tmp_path, with_mapping=False)
    client = RecordingNeo4jClient()

    with pytest.raises(ValueError, match="mode"):
        build_graph_index(article_path, mapping_path, client=client, mode="drop")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="batch_size"):
        build_graph_index(article_path, mapping_path, client=client, batch_size=0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_rows"):
        build_graph_index(article_path, mapping_path, client=client, max_rows=0)  # type: ignore[arg-type]

