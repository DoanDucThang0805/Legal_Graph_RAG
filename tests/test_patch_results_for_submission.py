from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest


ARTICLE_1 = "04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa|Điều 4"
ARTICLE_2 = "05/2018/QH14|Luật khác|Điều 5"
DOC_1 = "04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa"
DOC_2 = "05/2018/QH14|Luật khác"


def load_patch_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "patch_results_for_submission.py"
    spec = importlib.util.spec_from_file_location("patch_results_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_item(**overrides: Any) -> dict[str, Any]:
    item = {
        "id": 1,
        "question": "Câu hỏi?",
        "answer": "Theo Điều 4, nội dung trả lời.",
        "relevant_docs": [DOC_1],
        "relevant_articles": [ARTICLE_1],
    }
    item.update(overrides)
    return item


def test_import_script_does_not_run_patch(capsys) -> None:
    load_patch_module()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_validate_schema_passes_valid_sample() -> None:
    module = load_patch_module()

    module.validate_schema([sample_item()])


def test_validate_schema_missing_required_field_raises() -> None:
    module = load_patch_module()

    with pytest.raises(module.PatchError, match="missing required field"):
        module.validate_schema([{"id": 1}])


def test_removes_disclaimer_from_answer() -> None:
    module = load_patch_module()
    answer = "Theo Điều 4, được hỗ trợ. Lưu ý: Đây là thông tin tham khảo dựa trên căn cứ được cung cấp."

    patched, disclaimer_count, leakage_count = module.patch_answer(answer, module.PatchOptions())

    assert patched == "Theo Điều 4, được hỗ trợ."
    assert disclaimer_count == 1
    assert leakage_count == 0


def test_removes_internal_leakage_from_answer() -> None:
    module = load_patch_module()
    answer = "Theo thông tin được cung cấp trong selected_articles/context, doanh nghiệp được hỗ trợ theo Điều 4."

    patched, _, leakage_count = module.patch_answer(answer, module.PatchOptions())

    assert "selected_articles/context" not in patched
    assert patched == "doanh nghiệp được hỗ trợ theo Điều 4."
    assert leakage_count == 1


def test_deduplicates_docs_and_articles_preserving_order() -> None:
    module = load_patch_module()

    docs, articles, warnings, counters = module.patch_references(
        [DOC_1, DOC_2, DOC_1],
        [ARTICLE_1, ARTICLE_2, ARTICLE_1],
        options=module.PatchOptions(deduplicate_refs=True, remove_khong_so_refs=False),
    )

    assert docs == [DOC_1, DOC_2]
    assert articles == [ARTICLE_1, ARTICLE_2]
    assert warnings == []
    assert counters["duplicate_docs_removed"] == 1
    assert counters["duplicate_articles_removed"] == 1


def test_removes_khong_so_refs() -> None:
    module = load_patch_module()
    khong_so_article = "Không số|Văn bản Không số|Điều 1"
    khong_so_doc = "Không số|Văn bản Không số"

    docs, articles, warnings, counters = module.patch_references(
        [DOC_1, khong_so_doc],
        [ARTICLE_1, khong_so_article],
        options=module.PatchOptions(remove_khong_so_refs=True),
    )

    assert docs == [DOC_1]
    assert articles == [ARTICLE_1]
    assert warnings == []
    assert counters["khong_so_refs_removed"] == 2


def test_remove_khong_so_rollback_when_articles_would_be_empty() -> None:
    module = load_patch_module()
    khong_so_article = "Không số|Văn bản Không số|Điều 1"
    khong_so_doc = "Không số|Văn bản Không số"

    docs, articles, warnings, counters = module.patch_references(
        [khong_so_doc],
        [khong_so_article],
        options=module.PatchOptions(remove_khong_so_refs=True),
    )

    assert docs == [khong_so_doc]
    assert articles == [khong_so_article]
    assert warnings == ["removing Khong so refs would empty relevant_articles; rolled back refs"]
    assert counters["khong_so_refs_removed"] == 0


def test_optional_prune_keeps_top_n_articles() -> None:
    module = load_patch_module()
    article_3 = "06/2019/QH14|Luật thứ ba|Điều 6"

    docs, articles, warnings, counters = module.patch_references(
        [DOC_1, DOC_2, "06/2019/QH14|Luật thứ ba"],
        [ARTICLE_1, ARTICLE_2, article_3],
        options=module.PatchOptions(enable_prune=True, max_articles=2, max_docs=5),
    )

    assert articles == [ARTICLE_1, ARTICLE_2]
    assert docs == [DOC_1, DOC_2]
    assert warnings == []
    assert counters["pruned_articles_count"] == 1


def test_prune_syncs_docs_to_article_doc_ids() -> None:
    module = load_patch_module()

    docs, articles, _, _ = module.patch_references(
        [DOC_1, DOC_2],
        [ARTICLE_1, ARTICLE_2],
        options=module.PatchOptions(enable_prune=True, max_articles=1, max_docs=5),
    )

    assert articles == [ARTICLE_1]
    assert docs == [DOC_1]


def test_dry_run_does_not_write_outputs(tmp_path, capsys) -> None:
    module = load_patch_module()
    input_path = tmp_path / "results.json"
    output_path = tmp_path / "patched.json"
    report_path = tmp_path / "report.json"
    changes_path = tmp_path / "changes.jsonl"
    input_path.write_text(json.dumps([sample_item()], ensure_ascii=False), encoding="utf-8")

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--changes",
            str(changes_path),
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert not output_path.exists()
    assert not report_path.exists()
    assert not changes_path.exists()
    assert '"total_records": 1' in capsys.readouterr().out


def test_zip_output_is_flat_results_json_only(tmp_path) -> None:
    module = load_patch_module()
    input_path = tmp_path / "results.json"
    output_path = tmp_path / "patched.json"
    report_path = tmp_path / "report.json"
    changes_path = tmp_path / "changes.jsonl"
    zip_path = tmp_path / "submission.zip"
    input_path.write_text(json.dumps([sample_item()], ensure_ascii=False), encoding="utf-8")

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--changes",
            str(changes_path),
            "--zip-output",
            str(zip_path),
        ]
    )

    assert exit_code == 0
    with ZipFile(zip_path) as archive:
        assert archive.namelist() == ["results.json"]


def test_output_preserves_record_count_order_ids_and_questions() -> None:
    module = load_patch_module()
    items = [
        sample_item(id=2, question="Q2", relevant_articles=[ARTICLE_2], relevant_docs=[DOC_2]),
        sample_item(id=1, question="Q1"),
    ]

    patched, report, _ = module.patch_results_items(items, options=module.PatchOptions())

    assert [row["id"] for row in patched] == [2, 1]
    assert [row["question"] for row in patched] == ["Q2", "Q1"]
    assert len(patched) == len(items)
    assert report["output_records"] == 2


def test_patch_does_not_call_external_services(monkeypatch) -> None:
    module = load_patch_module()
    forbidden_imports = {
        "backend.retrieval.hybrid_retrieval",
        "backend.infrastructure.gen_llm_models.vllm_client",
        "backend.infrastructure.vector_store.qdrant_client",
        "backend.infrastructure.search_engine.opensearch_client",
        "backend.infrastructure.graph_store.neo4j_client",
    }

    real_import = __import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in forbidden_imports:
            raise AssertionError(f"unexpected external import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)

    patched, _, _ = module.patch_results_items([sample_item()], options=module.PatchOptions())

    assert patched[0]["id"] == 1
