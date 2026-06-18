from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


def load_script_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "02_build_indexes.py"
    spec = importlib.util.spec_from_file_location("build_indexes_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Calls:
    def __init__(self) -> None:
        self.items: list[tuple[str, dict[str, Any]]] = []

    def add(self, name: str, **kwargs: Any) -> None:
        self.items.append((name, kwargs))


def fake_builders(module: Any, calls: Calls) -> Any:
    def build_bm25(**kwargs: Any) -> None:
        calls.add("bm25", **kwargs)

    def build_vector(**kwargs: Any) -> None:
        calls.add("dense", **kwargs)

    def build_exact_duckdb(*args: Any, **kwargs: Any) -> None:
        calls.add("exact", args=args, **kwargs)

    def build_exact_json(*args: Any, **kwargs: Any) -> None:
        calls.add("legacy_json", args=args, **kwargs)

    def embedder_factory(**kwargs: Any) -> dict[str, Any]:
        calls.add("embedder", **kwargs)
        return {"embedder_kwargs": kwargs}

    def prepare_index_corpus() -> None:
        calls.add("prepare")

    return module.IndexBuilders(
        build_bm25=build_bm25,
        build_vector=build_vector,
        build_exact_duckdb=build_exact_duckdb,
        build_exact_json=build_exact_json,
        embedder_factory=embedder_factory,
        prepare_index_corpus=prepare_index_corpus,
    )


def create_required_inputs(processed_dir: Path) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "legal_article_chunks.parquet",
        "phapdien_articles_index.parquet",
        "anle_units.parquet",
        "legal_articles.parquet",
    ):
        (processed_dir / name).touch()


def test_without_only_prints_help_and_does_not_dispatch(tmp_path, capsys) -> None:
    module = load_script_module()
    calls = Calls()

    exit_code = module.main(["--processed-dir", str(tmp_path)], builders=fake_builders(module, calls))

    assert exit_code == 2
    assert calls.items == []
    assert "Build Phase 2 indexes" in capsys.readouterr().out


def test_only_bm25_dispatches_bm25_builder(tmp_path) -> None:
    module = load_script_module()
    create_required_inputs(tmp_path)
    calls = Calls()

    exit_code = module.main(
        ["--only", "bm25", "--processed-dir", str(tmp_path), "--recreate"],
        builders=fake_builders(module, calls),
    )

    assert exit_code == 0
    assert calls.items == [("bm25", {"recreate": True})]


def test_only_dense_dispatches_vector_builder(tmp_path) -> None:
    module = load_script_module()
    create_required_inputs(tmp_path)
    calls = Calls()

    exit_code = module.main(
        [
            "--only",
            "dense",
            "--processed-dir",
            str(tmp_path),
            "--device",
            "cuda",
            "--batch-size",
            "16",
            "--max-length",
            "512",
            "--max-rows",
            "20",
            "--no-resume",
        ],
        builders=fake_builders(module, calls),
    )

    assert exit_code == 0
    assert calls.items[0] == (
        "embedder",
        {"batch_size": 16, "max_length": 512, "device": "cuda"},
    )
    assert calls.items[1][0] == "dense"
    assert calls.items[1][1]["recreate"] is False
    assert calls.items[1][1]["resume"] is False
    assert calls.items[1][1]["max_rows"] == 20


def test_only_vector_alias_dispatches_vector_builder(tmp_path) -> None:
    module = load_script_module()
    create_required_inputs(tmp_path)
    calls = Calls()

    exit_code = module.main(
        ["--only", "vector", "--processed-dir", str(tmp_path)],
        builders=fake_builders(module, calls),
    )

    assert exit_code == 0
    assert [name for name, _ in calls.items] == ["embedder", "dense"]


def test_only_exact_dispatches_duckdb_builder_by_default(tmp_path) -> None:
    module = load_script_module()
    create_required_inputs(tmp_path)
    calls = Calls()

    exit_code = module.main(
        ["--only", "exact", "--processed-dir", str(tmp_path), "--recreate"],
        builders=fake_builders(module, calls),
    )

    assert exit_code == 0
    assert [name for name, _ in calls.items] == ["exact"]
    assert calls.items[0][1]["args"] == (tmp_path / "legal_articles.parquet", tmp_path / "exact_index.duckdb")
    assert calls.items[0][1]["recreate"] is True


def test_only_exact_duckdb_alias_dispatches_exact_builder(tmp_path) -> None:
    module = load_script_module()
    create_required_inputs(tmp_path)
    calls = Calls()

    exit_code = module.main(
        ["--only", "exact-duckdb", "--processed-dir", str(tmp_path)],
        builders=fake_builders(module, calls),
    )

    assert exit_code == 0
    assert [name for name, _ in calls.items] == ["exact"]


def test_all_no_dense_dispatches_only_bm25_and_exact(tmp_path) -> None:
    module = load_script_module()
    create_required_inputs(tmp_path)
    calls = Calls()

    exit_code = module.main(
        ["--only", "all-no-dense", "--processed-dir", str(tmp_path)],
        builders=fake_builders(module, calls),
    )

    assert exit_code == 0
    assert [name for name, _ in calls.items] == ["bm25", "exact"]


def test_missing_input_file_raises_clear_error(tmp_path) -> None:
    module = load_script_module()
    calls = Calls()

    with pytest.raises(FileNotFoundError) as exc_info:
        module.main(
            ["--only", "bm25", "--processed-dir", str(tmp_path)],
            builders=fake_builders(module, calls),
        )

    message = str(exc_info.value)
    assert "Missing required input file(s)" in message
    assert "prepare_index_corpus" in message
    assert "legal_article_chunks.parquet" in message
    assert calls.items == []
