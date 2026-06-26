from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest


ARTICLE_1 = "04/2017/QH14|Luáº­t há»— trá»£ doanh nghiá»‡p nhá» vÃ  vá»«a|Äiá»u 4"
ARTICLE_2 = "05/2018/QH14|Luáº­t khÃ¡c|Äiá»u 5"
DOC_1 = "04/2017/QH14|Luáº­t há»— trá»£ doanh nghiá»‡p nhá» vÃ  vá»«a"
DOC_2 = "05/2018/QH14|Luáº­t khÃ¡c"


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
        "question": "CÃ¢u há»i?",
        "answer": "Theo Äiá»u 4, ná»™i dung tráº£ lá»i.",
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
    answer = "Theo Äiá»u 4, Ä‘Æ°á»£c há»— trá»£. LÆ°u Ã½: ÄÃ¢y lÃ  thÃ´ng tin tham kháº£o dá»±a trÃªn cÄƒn cá»© Ä‘Æ°á»£c cung cáº¥p."

    patched, disclaimer_count, leakage_count = module.patch_answer(answer, module.PatchOptions())

    assert patched == "Theo Äiá»u 4, Ä‘Æ°á»£c há»— trá»£."
    assert disclaimer_count == 1
    assert leakage_count == 0



def test_removes_residual_thong_tin_tham_khao_disclaimer_lines() -> None:
    module = load_patch_module()
    variants = [
        "Th\u00f4ng tin tham kh\u1ea3o d\u1ef1a tr\u00ean c\u0103n c\u1ee9 \u0111\u01b0\u1ee3c cung c\u1ea5p.",
        "L\u01b0u \u00fd: Th\u00f4ng tin tham kh\u1ea3o d\u1ef1a tr\u00ean c\u0103n c\u1ee9 [A2].",
        "L\u01b0u \u00fd th\u00f4ng tin tham kh\u1ea3o: C\u0103n c\u1ee9 \u0110i\u1ec1u 84",
        "Th\u00f4ng tin tham kh\u1ea3o d\u1ef1a tr\u00ean c\u0103n c\u1ee9 [A1], [A2].",
        "L\u01b0u \u00fd: \u0110\u00e2y l\u00e0 th\u00f4ng tin tham kh\u1ea3o d\u1ef1a",
        "L\u01b0u \u00fd: \u0110\u00e2y l\u00e0 th\u00f4ng tin tham kh\u1ea3o d\u1ef1a tr\u00ean c\u0103n c\u1ee9 \u0111\u01b0\u1ee3c",
        "L\u01b0u \u00fd: \u0110\u00e2y l\u00e0 th\u00f4ng tin tham kh\u1ea3o",
        "L\u01b0u \u00fd \u0111\u00e2y l\u00e0 th\u00f4ng tin tham kh\u1ea3o d\u1ef1a tr\u00ean c\u0103n c\u1ee9",
    ]
    answer = "Theo \u0110i\u1ec1u 4, n\u1ed9i dung ch\u00ednh.\n" + "\n".join(variants)

    patched, disclaimer_count, _ = module.patch_answer(answer, module.PatchOptions())

    assert patched == "Theo \u0110i\u1ec1u 4, n\u1ed9i dung ch\u00ednh."
    assert disclaimer_count == len(variants)



def test_does_not_remove_non_disclaimer_tham_khao_line() -> None:
    module = load_patch_module()
    answer = "Doanh nghi\u1ec7p c\u00f3 th\u1ec3 tham kh\u1ea3o quy \u0111\u1ecbnh t\u1ea1i \u0110i\u1ec1u 4."

    patched, disclaimer_count, _ = module.patch_answer(answer, module.PatchOptions())

    assert patched == answer
    assert disclaimer_count == 0



def test_answer_cleanup_rollback_when_only_disclaimer() -> None:
    module = load_patch_module()
    item = sample_item(answer="Th\u00f4ng tin tham kh\u1ea3o d\u1ef1a tr\u00ean c\u0103n c\u1ee9 [A1].")
    stats = module.PatchStats()

    patched, change = module.patch_record(item, options=module.PatchOptions(), stats=stats)

    assert patched["answer"] == item["answer"]
    assert "rolled back answer" in change.warnings[0]
    assert stats.rollback_count == 1

def test_removes_internal_leakage_from_answer() -> None:
    module = load_patch_module()
    answer = "Theo thÃ´ng tin Ä‘Æ°á»£c cung cáº¥p trong selected_articles/context, doanh nghiá»‡p Ä‘Æ°á»£c há»— trá»£ theo Äiá»u 4."

    patched, _, leakage_count = module.patch_answer(answer, module.PatchOptions())

    assert "selected_articles/context" not in patched
    assert patched == "doanh nghiá»‡p Ä‘Æ°á»£c há»— trá»£ theo Äiá»u 4."
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
    khong_so_article = "KhÃ´ng sá»‘|VÄƒn báº£n KhÃ´ng sá»‘|Äiá»u 1"
    khong_so_doc = "KhÃ´ng sá»‘|VÄƒn báº£n KhÃ´ng sá»‘"

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
    khong_so_article = "KhÃ´ng sá»‘|VÄƒn báº£n KhÃ´ng sá»‘|Äiá»u 1"
    khong_so_doc = "KhÃ´ng sá»‘|VÄƒn báº£n KhÃ´ng sá»‘"

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
    article_3 = "06/2019/QH14|Luáº­t thá»© ba|Äiá»u 6"

    docs, articles, warnings, counters = module.patch_references(
        [DOC_1, DOC_2, "06/2019/QH14|Luáº­t thá»© ba"],
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

