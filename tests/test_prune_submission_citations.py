from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from zipfile import ZipFile


def load_prune_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "prune_submission_citations.py"
    spec = importlib.util.spec_from_file_location("prune_submission_citations_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def article(law_id: str, title: str = "Luáº­t Doanh nghiá»‡p", article_no: str = "Äiá»u 4") -> str:
    return f"{law_id}|{title}|{article_no}"


def doc(law_id: str, title: str = "Luáº­t Doanh nghiá»‡p") -> str:
    return f"{law_id}|{title}"


def item(question: str, answer: str, articles: list[str], docs: list[str] | None = None) -> dict[str, Any]:
    module = load_prune_module()
    return {
        "id": 1,
        "question": question,
        "answer": answer,
        "relevant_docs": docs if docs is not None else module.rebuild_docs_from_articles(articles),
        "relevant_articles": articles,
    }


def test_parse_article_ref() -> None:
    module = load_prune_module()

    parsed = module.parse_article_ref("38/2019/QH14|Luáº­t Quáº£n lÃ½ thuáº¿|Äiá»u 3")

    assert parsed.law_id == "38/2019/QH14"
    assert parsed.law_title == "Luáº­t Quáº£n lÃ½ thuáº¿"
    assert parsed.article_no == "Äiá»u 3"
    assert parsed.doc_ref == "38/2019/QH14|Luáº­t Quáº£n lÃ½ thuáº¿"


def test_deduplicate_preserve_order() -> None:
    module = load_prune_module()

    assert module.deduplicate_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_local_document_penalty_without_local_indicator() -> None:
    module = load_prune_module()
    refs = [
        module.parse_article_ref(article("01/2020/QÄ-UBND", "QÄ-UBND HÃ  Ná»™i", "Äiá»u 1")),
        module.parse_article_ref(article("38/2019/QH14", "Luáº­t Quáº£n lÃ½ thuáº¿", "Äiá»u 1")),
    ]

    scored = module.score_articles(refs, question="Doanh nghiá»‡p Ä‘Æ°á»£c há»— trá»£ gÃ¬?", answer="Theo Äiá»u 1.", variant="a")

    assert scored[0].score < scored[1].score
    assert "local_penalty" in scored[0].reasons


def test_conflict_old_new_penalty() -> None:
    module = load_prune_module()
    old_ref = module.parse_article_ref(article("78/2006/QH11", "Luáº­t Quáº£n lÃ½ thuáº¿", "Äiá»u 1"))
    new_ref = module.parse_article_ref(article("38/2019/QH14", "Luáº­t Quáº£n lÃ½ thuáº¿", "Äiá»u 2"))

    scored = module.score_articles([old_ref, new_ref], question="Thuáº¿ tháº¿ nÃ o?", answer="Theo Äiá»u 2.", variant="a")

    assert "old_new_conflict_penalty" in scored[0].reasons
    assert scored[0].score < scored[1].score


def test_caps_by_question_type_variant_a_and_b() -> None:
    module = load_prune_module()

    assert module.caps_for_variant("a", module.determine_question_type("Thá»i háº¡n bao lÃ¢u?")).max_articles == 3
    assert module.caps_for_variant("a", module.determine_question_type("Bao gá»“m nhá»¯ng chÃ­nh sÃ¡ch nÃ o?")).max_articles == 5
    assert module.caps_for_variant("b", module.determine_question_type("Thá»i háº¡n bao lÃ¢u?")).max_articles == 2
    assert module.caps_for_variant("b", "default").max_docs == 2


def test_docs_are_rebuilt_from_remaining_articles() -> None:
    module = load_prune_module()
    articles = [
        article("38/2019/QH14", "Luáº­t Quáº£n lÃ½ thuáº¿", "Äiá»u 1"),
        article("22/2023/QH15", "Luáº­t Äáº¥u tháº§u", "Äiá»u 2"),
    ]
    record = item(
        "Thá»i háº¡n bao lÃ¢u?",
        "Theo Äiá»u 1.",
        articles,
        docs=[doc("38/2019/QH14", "Luáº­t Quáº£n lÃ½ thuáº¿"), doc("99/9999/XX", "Luáº­t nhiá»…u")],
    )

    patched, _ = module.prune_record(record, variant="b")

    assert patched["relevant_docs"] == [doc("38/2019/QH14", "Luáº­t Quáº£n lÃ½ thuáº¿")]
    assert patched["relevant_articles"] == [articles[0]]


def test_rollback_if_pruning_would_empty_refs() -> None:
    module = load_prune_module()
    record = item("CÃ¢u há»i?", "Tráº£ lá»i.", ["bad-format"], docs=["bad-doc"])

    patched, change = module.prune_record(record, variant="a")

    assert patched == record
    assert change["rolled_back"] is True
    assert change["warnings"]


def test_variant_a_keeps_more_than_variant_b() -> None:
    module = load_prune_module()
    articles = [article("01/2020/QH14", "Luật A", f"Điều {i}") for i in range(1, 6)]
    record = item("CÃ¢u há»i máº·c Ä‘á»‹nh?", "Theo Äiá»u 1.", articles)

    patched_a, _ = module.prune_record(record, variant="a")
    patched_b, _ = module.prune_record(record, variant="b")

    assert len(patched_a["relevant_articles"]) == 4
    assert len(patched_b["relevant_articles"]) == 3


def test_variant_c_prefers_articles_mentioned_in_answer() -> None:
    module = load_prune_module()
    articles = [
        article("01/2020/QH14", "Luáº­t A", "Äiá»u 1"),
        article("02/2020/QH14", "Luáº­t B", "Äiá»u 2"),
        article("03/2020/QH14", "Luáº­t C", "Äiá»u 3"),
    ]
    record = item("CÃ¡c chÃ­nh sÃ¡ch nÃ o?", "CÄƒn cá»© Äiá»u 2.", articles)

    patched, _ = module.prune_record(record, variant="c")

    assert patched["relevant_articles"] == [articles[1]]
    assert patched["relevant_docs"] == [doc("02/2020/QH14", "Luáº­t B")]


def test_variant_c_backfills_when_no_article_is_mentioned() -> None:
    module = load_prune_module()
    articles = [article("01/2020/QH14", "Luáº­t A", "Äiá»u 1")]
    record = item("CÃ¢u há»i?", "KhÃ´ng nháº¯c Ä‘iá»u cá»¥ thá»ƒ.", articles)

    patched, change = module.prune_record(record, variant="c")

    assert patched["relevant_articles"] == articles
    assert change["rolled_back"] is False


def test_zip_output_contains_only_root_results_json(tmp_path) -> None:
    module = load_prune_module()
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    report_path = tmp_path / "report.json"
    changes_path = tmp_path / "changes.jsonl"
    zip_path = tmp_path / "submission.zip"
    record = item("CÃ¢u há»i?", "Theo Äiá»u 1.", [article("01/2020/QH14", "Luáº­t A", "Äiá»u 1")])
    input_path.write_text(json.dumps([record], ensure_ascii=False), encoding="utf-8")

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
            "--variant",
            "a",
        ]
    )

    assert exit_code == 0
    with ZipFile(zip_path) as archive:
        assert archive.namelist() == ["results.json"]
