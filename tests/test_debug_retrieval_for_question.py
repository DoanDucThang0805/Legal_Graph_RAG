from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import polars as pl


def load_debug_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "debug_retrieval_for_question.py"
    spec = importlib.util.spec_from_file_location("debug_retrieval_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows: list[dict[str, Any] | list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


def test_import_script_does_not_run_debug(capsys) -> None:
    load_debug_module()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_load_question_by_id_reads_parquet(tmp_path) -> None:
    module = load_debug_module()
    question_path = tmp_path / "questions.parquet"
    pl.DataFrame(
        [
            {"id": 1, "question": "Câu hỏi một", "domain": "tax"},
            {"id": 2, "question": "Câu hỏi hai", "domain": "labor"},
        ]
    ).write_parquet(question_path)
    warnings: list[str] = []

    row = module.load_question_by_id(question_path, 2, warnings)

    assert row["question"] == "Câu hỏi hai"
    assert warnings == []


def test_load_retrieval_record_by_id_reads_matching_jsonl(tmp_path) -> None:
    module = load_debug_module()
    retrieval_path = tmp_path / "retrieval.jsonl"
    write_jsonl(
        retrieval_path,
        [
            {"id": 1, "question": "Q1"},
            {"question_id": 2, "question_text": "Q2", "selected_article_ids": ["a2"]},
        ],
    )

    record, warnings = module.load_retrieval_record_by_id(retrieval_path, 2)

    assert record["question_text"] == "Q2"
    assert warnings == []


def test_load_retrieval_record_by_id_returns_none_when_missing(tmp_path) -> None:
    module = load_debug_module()
    retrieval_path = tmp_path / "retrieval.jsonl"
    write_jsonl(retrieval_path, [{"id": 1, "question": "Q1"}])

    record, warnings = module.load_retrieval_record_by_id(retrieval_path, 99)

    assert record is None
    assert warnings == []


def test_duplicate_retrieval_records_warn_and_use_first(tmp_path) -> None:
    module = load_debug_module()
    retrieval_path = tmp_path / "retrieval.jsonl"
    write_jsonl(
        retrieval_path,
        [
            {"id": 1, "question": "first"},
            {"id": 1, "question": "second"},
        ],
    )

    record, warnings = module.load_retrieval_record_by_id(retrieval_path, 1)

    assert record["question"] == "first"
    assert "using the first record" in warnings[0]


def test_pretty_formatter_contains_main_sections() -> None:
    module = load_debug_module()
    payload = {
        "question": {"id": 1, "text": "Doanh nghiệp hỏi gì?"},
        "analysis": {"domain": "business", "answer_type": "procedure", "complexity": "single", "stage_counts": {}, "errors": {}},
        "bm25_hits": [],
        "dense_hits": [],
        "exact_hits": [],
        "phapdien_hits": [],
        "rrf_merged": [],
        "selected_articles": [{"rank": 1, "article_id": "LAW|Title|Điều 1"}],
        "warnings": [],
    }

    output = module.format_debug_payload(payload)

    for section in (
        "[QUESTION]",
        "[ANALYSIS]",
        "[BM25 HITS]",
        "[DENSE HITS]",
        "[EXACT HITS]",
        "[PHAPDIEN HITS]",
        "[RRF MERGED]",
        "[SELECTED ARTICLES]",
        "[WARNINGS]",
    ):
        assert section in output


def test_top_k_limits_hits() -> None:
    module = load_debug_module()
    hits = [{"article_id": f"a{i}"} for i in range(5)]

    normalized = module.normalize_hit_group(hits, top_k=2, show_text=False, max_text_chars=100)

    assert [item["article_id"] for item in normalized] == ["a0", "a1"]


def test_truncate_text_compacts_and_truncates() -> None:
    module = load_debug_module()

    assert module.truncate_text("a   b   c", 20) == "a b c"
    assert module.truncate_text("abcdefghijklmnopqrstuvwxyz", 10) == "abcdefg..."


def test_main_with_retrieval_file_returns_zero(tmp_path, capsys) -> None:
    module = load_debug_module()
    retrieval_path = tmp_path / "retrieval.jsonl"
    question_path = tmp_path / "questions.parquet"
    write_jsonl(
        retrieval_path,
        [
            {
                "id": 1,
                "question": "Q1",
                "domain": "tax",
                "answer_type": "deadline",
                "complexity": "single",
                "bm25_hits": [{"article_id": "a1", "score": 1.0}],
                "selected_articles": ["a1"],
            }
        ],
    )
    pl.DataFrame([{"id": 1, "question": "Q1 analyzed"}]).write_parquet(question_path)

    exit_code = module.main(
        [
            "--id",
            "1",
            "--use-current-retrieval-file",
            "--retrieval-file",
            str(retrieval_path),
            "--questions-file",
            str(question_path),
            "--top-k",
            "5",
        ]
    )

    assert exit_code == 0
    assert "[SELECTED ARTICLES]" in capsys.readouterr().out


def test_main_with_missing_id_returns_non_zero(tmp_path, capsys) -> None:
    module = load_debug_module()
    retrieval_path = tmp_path / "retrieval.jsonl"
    write_jsonl(retrieval_path, [{"id": 1, "question": "Q1"}])

    exit_code = module.main(["--id", "999", "--retrieval-file", str(retrieval_path)])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().out


def test_offline_mode_does_not_import_live_retriever(tmp_path, monkeypatch) -> None:
    module = load_debug_module()
    retrieval_path = tmp_path / "retrieval.jsonl"
    write_jsonl(retrieval_path, [{"id": 1, "question": "Q1", "selected_articles": ["a1"]}])

    class BlockingFinder:
        def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
            if fullname == "backend.retrieval.hybrid_retrieval":
                raise AssertionError("offline mode must not import HybridLegalRetriever")
            return None

    finder = BlockingFinder()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    exit_code = module.main(["--id", "1", "--retrieval-file", str(retrieval_path)])

    assert exit_code == 0


def test_live_mode_uses_existing_orchestrator_when_explicit(tmp_path, monkeypatch, capsys) -> None:
    module = load_debug_module()
    question_path = tmp_path / "questions.parquet"
    pl.DataFrame([{"id": 1, "question": "Q1", "answer_type": "general", "complexity": "single"}]).write_parquet(question_path)

    class FakeResult:
        question = "Q1"
        candidates: list[Any] = []
        selected_article_ids = ["a1"]
        selected_candidates: list[Any] = []
        debug = {"stage_counts": {"selected_candidates": 1}, "errors": {}}

    class FakeHybridLegalRetriever:
        called = False

        def retrieve(self, payload: dict[str, Any], *, top_k: int) -> FakeResult:
            FakeHybridLegalRetriever.called = True
            assert payload["question"] == "Q1"
            assert top_k == 3
            return FakeResult()

    fake_module = types.ModuleType("backend.retrieval.hybrid_retrieval")
    fake_module.HybridLegalRetriever = FakeHybridLegalRetriever
    monkeypatch.setitem(sys.modules, "backend.retrieval.hybrid_retrieval", fake_module)

    exit_code = module.main(["--id", "1", "--live", "--questions-file", str(question_path), "--top-k", "3"])

    assert exit_code == 0
    assert FakeHybridLegalRetriever.called is True
    assert "Live mode uses existing HybridLegalRetriever" in capsys.readouterr().out
