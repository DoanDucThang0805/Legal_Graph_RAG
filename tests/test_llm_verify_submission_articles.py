from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


def load_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "llm_verify_submission_articles.py"
    spec = importlib.util.spec_from_file_location("llm_verify_submission_articles_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def article(law_id: str, title: str = "Luật A", article_no: str = "Điều 1") -> str:
    return f"{law_id}|{title}|{article_no}"


def record(articles: list[str], record_id: int = 1, question: str = "Nộp thuế thế nào?", answer: str = "Theo Điều 1.") -> dict[str, Any]:
    module = load_module()
    return {"id": record_id, "question": question, "answer": answer, "relevant_docs": module.rebuild_docs_from_articles(articles), "relevant_articles": articles}


def options(mode: str = "balanced") -> dict[str, Any]:
    return {"mode": mode, "max_candidates": 12, "max_article_chars": 1200, "limit": None, "start_id": None, "end_id": None, "only_possible_overpruned": False, "priority_domains": "", "sleep_seconds": 0}


def test_parse_article_ref() -> None:
    module = load_module()
    ref = module.parse_article_ref("38/2019/QH14|Luật Quản lý thuế|Điều 3")
    assert ref.law_id == "38/2019/QH14"
    assert ref.law_title == "Luật Quản lý thuế"
    assert ref.article_no == "Điều 3"
    assert ref.doc_ref == "38/2019/QH14|Luật Quản lý thuế"
    assert module.parse_article_ref("bad") is None


def test_article_text_lookup_exact_key() -> None:
    module = load_module()
    lookup = module.build_article_text_lookup([{"law_id": "01/2020/QH14", "law_title": "Luật A", "article_no": "Điều 1", "article_text": "text exact"}])
    ref = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 1"))
    assert module.lookup_article_text(lookup, ref) == ("text exact", None, False)


def test_article_text_lookup_fallback_law_id_article_no() -> None:
    module = load_module()
    lookup = module.build_article_text_lookup([{"law_id": "01/2020/QH14", "law_title": "Luật khác", "article_no": "Điều 1", "article_text": "fallback text"}])
    ref = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 1"))
    text, warning, missing = module.lookup_article_text(lookup, ref)
    assert text == "fallback text"
    assert warning is None
    assert missing is False


def test_candidate_ordering_with_fallback_and_audit_risky_fields() -> None:
    module = load_module()
    articles = [article(f"0{i}/2020/QH14", f"Luật {i}", f"Điều {i}") for i in range(1, 6)]
    audit = {"answer_mentioned_removed_articles": articles[3], "legal_basis_removed_articles": articles[4], "domain_primary_removed_articles": articles[2]}
    ordered = module.order_candidate_refs(articles, [articles[1]], audit, max_candidates=4)
    assert [ref.raw for ref in ordered] == [articles[1], articles[3], articles[4], articles[2]]


def test_prompt_candidate_formatting() -> None:
    module = load_module()
    ref = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 1"))
    candidate = module.Candidate(1, ref, "Nội dung điều luật", 0)
    prompt = module.format_user_prompt("Câu hỏi?", [candidate])
    assert "[1]" in prompt
    assert "article_ref: 01/2020/QH14|Luật A|Điều 1" in prompt
    assert "article_text:" in prompt


def test_json_parsing_direct_and_fenced_noisy_output() -> None:
    module = load_module()
    direct = '{"selected": [], "rejected": []}'
    fenced = 'noise```json\n{"selected": [], "rejected": []}\n```tail'
    assert module.parse_llm_json(direct)["selected"] == []
    assert module.parse_llm_json(fenced)["rejected"] == []


def test_label_normalization_and_confidence_clamping() -> None:
    module = load_module()
    assert module.normalize_label("direct") == "direct_relevant"
    assert module.normalize_label("supporting") == "strong_supporting"
    assert module.normalize_label("old_law") == "superseded_old_law"
    assert module.clamp_confidence(2) == 1.0
    assert module.clamp_confidence(-1) == 0.0


def test_mode_thresholds() -> None:
    module = load_module()
    assert module.passes_mode_threshold("direct_relevant", 0.75, mode="strict", question_type="default")
    assert not module.passes_mode_threshold("strong_supporting", 0.90, mode="strict", question_type="default")
    assert module.passes_mode_threshold("strong_supporting", 0.60, mode="balanced", question_type="default")
    assert module.passes_mode_threshold("weak_supporting", 0.70, mode="balanced", question_type="list_policy")
    assert module.passes_mode_threshold("direct_relevant", 0.50, mode="recall", question_type="default")


def test_question_type_detection() -> None:
    module = load_module()
    assert module.detect_question_type("Thời hạn bao lâu?") == "single_fact"
    assert module.detect_question_type("Câu hỏi chung?") == "default"
    assert module.detect_question_type("Hồ sơ bao gồm những gì?") == "list_policy"
    assert module.detect_question_type("Vừa nộp thuế vừa bị phạt thì sao?") == "multi_part"


def test_fallback_on_invalid_json_and_empty_selection() -> None:
    module = load_module()
    articles = [article("01/2020/QH14", "Luật A", "Điều 1"), article("02/2020/QH14", "Luật B", "Điều 2")]
    original = record(articles)
    fallback = record([articles[0]])
    lookup = module.build_article_text_lookup([])
    patched, change = module.verify_record(record=original, fallback=fallback, audit={}, article_lookup=lookup, prompt_template="prompt", options=options(), llm_client=lambda _messages: "not json", domain="tax", question_type="default")
    assert patched["relevant_articles"] == [articles[0]]
    assert change["fallback_used"] is True
    patched2, change2 = module.verify_record(record=original, fallback=fallback, audit={}, article_lookup=lookup, prompt_template="prompt", options=options(), llm_client=lambda _messages: '{"selected": [], "rejected": [{"candidate_id": 1, "label": "irrelevant", "confidence": 1}]}', domain="tax", question_type="default")
    assert patched2["relevant_articles"] == [articles[0]]
    assert change2["fallback_used"] is True


def test_never_empty_articles_and_rebuild_docs() -> None:
    module = load_module()
    original = record([article("01/2020/QH14", "Luật A", "Điều 1")])
    empty_fallback = {**original, "relevant_docs": [], "relevant_articles": []}
    patched = module.fallback_or_top_original(original, empty_fallback)
    assert patched["relevant_articles"]
    assert patched["relevant_docs"] == ["01/2020/QH14|Luật A"]
    assert module.rebuild_docs_from_articles([article("01/2020/QH14", "Luật A", "Điều 1"), article("01/2020/QH14", "Luật A", "Điều 2")]) == ["01/2020/QH14|Luật A"]


def test_flat_zip_output(tmp_path: Path) -> None:
    module = load_module()
    output = tmp_path / "submission.zip"
    module.write_flat_zip(output, [record([article("01/2020/QH14", "Luật A", "Điều 1")])])
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["results.json"]


def test_report_field_creation() -> None:
    module = load_module()
    original = record([article("01/2020/QH14", "Luật A", "Điều 1")])
    change = module.build_change(original, original, mode="balanced", domain="tax", question_type="default", possible_overpruned=True, llm_success=True, fallback_used=False, warnings=[])
    report = module.build_report([original], [original], [change], module.Counter({"llm_success_count": 1}), module.Counter({"direct_relevant": 1}), module.Counter({"irrelevant": 1}), module.Counter({"tax": 1}), module.Counter(), {}, options())
    assert report["total_records"] == 1
    assert report["mode"] == "balanced"
    assert "domain_summary" in report
