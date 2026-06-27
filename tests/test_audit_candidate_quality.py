from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def load_audit_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_candidate_quality.py"
    spec = importlib.util.spec_from_file_location("audit_candidate_quality_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def article(law_id: str, title: str = "Luật Doanh nghiệp", article_no: str = "Điều 4") -> str:
    return f"{law_id}|{title}|{article_no}"


def record(record_id: int, question: str, answer: str, articles: list[str]) -> dict[str, Any]:
    module = load_audit_module()
    return {
        "id": record_id,
        "question": question,
        "answer": answer,
        "relevant_docs": [ref.doc_ref for ref in module.parse_article_refs(articles)],
        "relevant_articles": articles,
    }


def test_parse_article_ref() -> None:
    module = load_audit_module()

    parsed = module.parse_article_ref("38/2019/QH14|Luật Quản lý thuế|Điều 3")

    assert parsed.law_id == "38/2019/QH14"
    assert parsed.law_title == "Luật Quản lý thuế"
    assert parsed.article_no == "Điều 3"
    assert parsed.doc_ref == "38/2019/QH14|Luật Quản lý thuế"
    assert module.parse_article_ref("bad ref") is None


def test_extract_legal_basis_section() -> None:
    module = load_audit_module()
    answer = "Theo Điều 1.\nCăn cứ pháp lý:\n- Điều 5 Luật A"

    section = module.extract_legal_basis_section(answer)

    assert "can cu phap ly" in section
    assert "dieu 5" in section
    assert "dieu 1" not in section


def test_is_answer_mentioned_article() -> None:
    module = load_audit_module()
    ref_by_law = module.parse_article_ref(article("38/2019/QH14", "Luật Quản lý thuế", "Điều 99"))
    ref_by_article = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 5"))

    assert module.is_answer_mentioned_article(ref_by_law, "Theo 38/2019/QH14.")
    assert module.is_answer_mentioned_article(ref_by_article, "Theo Điều 5.")


def test_is_legal_basis_article() -> None:
    module = load_audit_module()
    ref = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 5"))
    answer = "Theo Điều 1.\nCăn cứ pháp lý:\n- Điều 5"

    assert module.is_legal_basis_article(ref, answer)


def test_detect_domain() -> None:
    module = load_audit_module()

    assert module.detect_domain("Doanh nghiệp nộp thuế thế nào?") == "tax"
    assert module.detect_domain("Người lao động đóng bảo hiểm xã hội ra sao?") == "labor_social_insurance"
    assert module.detect_domain("Hồ sơ dự thầu gồm gì?") == "bidding"
    assert module.detect_domain("Một câu hỏi không rõ lĩnh vực") == "other"


def test_is_local_doc() -> None:
    module = load_audit_module()

    assert module.is_local_doc("01/2020/QĐ-UBND|QĐ-UBND Hà Nội", "Doanh nghiệp được hỗ trợ gì?")
    assert not module.is_local_doc("01/2020/QĐ-UBND|QĐ-UBND Hà Nội", "Doanh nghiệp tại Hà Nội được hỗ trợ gì?")


def test_old_new_conflict_detection() -> None:
    module = load_audit_module()
    refs = module.parse_article_refs(
        [
            article("78/2006/QH11", "Luật Quản lý thuế", "Điều 1"),
            article("38/2019/QH14", "Luật Quản lý thuế", "Điều 2"),
        ]
    )

    assert module.has_old_new_conflict(refs)
    assert module.is_old_law_removed_with_new_retained(refs[0], [refs[1]], "Theo Điều 2 của 38/2019/QH14.")


def test_possible_overpruned_flag() -> None:
    module = load_audit_module()

    assert module.is_possible_overpruned(
        original_articles_count=6,
        pruned_articles_count=3,
        answer_mentioned_removed_count=1,
        legal_basis_removed_count=0,
        domain_primary_removed_count=0,
    )
    assert not module.is_possible_overpruned(
        original_articles_count=5,
        pruned_articles_count=3,
        answer_mentioned_removed_count=1,
        legal_basis_removed_count=0,
        domain_primary_removed_count=0,
    )


def test_risk_score_ordering() -> None:
    module = load_audit_module()

    low = module.compute_risk_score(
        answer_mentioned_removed_count=0,
        legal_basis_removed_count=0,
        domain_primary_removed_count=1,
        is_list_policy=False,
        original_articles_count=6,
        local_noisy_removed_count=1,
        old_law_removed_new_retained_count=0,
    )
    high = module.compute_risk_score(
        answer_mentioned_removed_count=1,
        legal_basis_removed_count=1,
        domain_primary_removed_count=1,
        is_list_policy=True,
        original_articles_count=7,
        local_noisy_removed_count=0,
        old_law_removed_new_retained_count=0,
    )

    assert high > low


def test_audit_record_marks_possible_overpruned() -> None:
    module = load_audit_module()
    articles = [article("01/2020/QH14", "Luật A", f"Điều {index}") for index in range(1, 7)]
    original = record(1, "Các điều kiện gì được áp dụng?", "Theo Điều 1, Điều 2 và Điều 6.", articles)
    pruned = record(1, original["question"], original["answer"], articles[:3])

    row = module.audit_record(original, pruned)

    assert row["removed_articles_count"] == 3
    assert row["answer_mentioned_removed_count"] == 1
    assert row["possible_overpruned"] is True
    assert articles[5] in row["answer_mentioned_removed_articles"]
