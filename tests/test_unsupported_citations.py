from backend.evaluation.unsupported_citations import (
    build_supported_citation_keys,
    detect_unsupported_citations,
    extract_answer_citations,
)


def test_supported_citation_is_not_flagged() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 27"}]
    answer = "Theo Điều 27, Nghị định 65/2023/NĐ-CP thì doanh nghiệp phải thực hiện..."

    assert detect_unsupported_citations(answer, selected_articles) == []


def test_unsupported_article_in_same_law_is_flagged() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 31"}]
    answer = "Theo Điều 27, Nghị định 65/2023/NĐ-CP thì doanh nghiệp phải thực hiện..."

    unsupported = detect_unsupported_citations(answer, selected_articles)

    assert len(unsupported) == 1
    assert unsupported[0].article_no == "Điều 27"
    assert unsupported[0].law_id == "65/2023/NĐ-CP"
    assert len(unsupported[0].raw_text) <= 150


def test_unsupported_law_is_flagged() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 27"}]
    answer = "Theo Điều 10, Thông tư 01/2007/TT-BKHCN thì hồ sơ gồm..."

    unsupported = detect_unsupported_citations(answer, selected_articles)

    assert len(unsupported) == 1
    assert unsupported[0].article_no == "Điều 10"
    assert unsupported[0].law_id == "01/2007/TT-BKHCN"


def test_weak_article_only_citation_is_not_flagged() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 27"}]
    answer = "Theo Điều 27, thời hạn là 10 ngày làm việc."

    assert extract_answer_citations(answer) == []
    assert detect_unsupported_citations(answer, selected_articles) == []


def test_canonical_string_selected_article_is_supported() -> None:
    selected_articles = ["65/2023/NĐ-CP|Nghị định 65/2023/NĐ-CP về việc thử nghiệm|Điều 27"]
    answer = "Theo Điều 27, Nghị định 65/2023/NĐ-CP thì doanh nghiệp phải thực hiện..."

    assert build_supported_citation_keys(selected_articles) == {("điều 27", "65/2023/nđ-cp")}
    assert detect_unsupported_citations(answer, selected_articles) == []


def test_multiple_citations_only_flags_unsupported_one() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 27"}]
    answer = (
        "Theo Điều 27, Nghị định 65/2023/NĐ-CP thì được áp dụng. "
        "Ngoài ra, Điều 10, Thông tư 01/2007/TT-BKHCN quy định hồ sơ khác."
    )

    unsupported = detect_unsupported_citations(answer, selected_articles)

    assert len(unsupported) == 1
    assert unsupported[0].article_no == "Điều 10"
    assert unsupported[0].law_id == "01/2007/TT-BKHCN"


def test_normalizes_article_number_and_law_id_variants() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 4"}]
    answer = "Theo điều 04 Nghị định 65/2023/ND-CP thì áp dụng quy định này."

    assert detect_unsupported_citations(answer, selected_articles) == []


def test_detects_required_strong_patterns() -> None:
    answer = (
        "Điều 27 Nghị định 65/2023/NĐ-CP; "
        "Điều 134 của Luật 36/2009/QH12; "
        "Điều 126 Luật 50/2005/QH11."
    )

    citations = extract_answer_citations(answer)

    assert [(citation.article_no, citation.law_id) for citation in citations] == [
        ("Điều 27", "65/2023/NĐ-CP"),
        ("Điều 134", "36/2009/QH12"),
        ("Điều 126", "50/2005/QH11"),
    ]


def test_does_not_join_article_to_law_id_across_legal_basis_block() -> None:
    selected_articles = [{"law_id": "80/2021/NĐ-CP", "article_no": "Điều 4"}]
    answer = (
        "Theo Điều 16, hộ kinh doanh cần đáp ứng điều kiện. "
        "Lưu ý đây là thông tin tham khảo dựa trên căn cứ được cung cấp.\n\n"
        "Căn cứ pháp lý:\n- Điều 4 - 80/2021/NĐ-CP"
    )

    citations = extract_answer_citations(answer)

    assert ("Điều 16", "80/2021/NĐ-CP") not in [
        (citation.article_no, citation.law_id) for citation in citations
    ]
    assert detect_unsupported_citations(answer, selected_articles) == []
    assert all("Căn cứ pháp lý" not in citation.raw_text for citation in citations)
    assert all("Lưu ý" not in citation.raw_text for citation in citations)


def test_does_not_join_article_to_law_id_across_long_answer_text() -> None:
    selected_articles = [{"law_id": "177/2015/TT-BTC", "article_no": "Điều 40"}]
    answer = (
        "Theo Điều 144, người lao động chưa thành niên cần được bảo vệ. "
        "Nội dung khác rất dài để mô tả quyền và nghĩa vụ trong quan hệ lao động. "
        "Căn cứ pháp lý: - Điều 40 - 177/2015/TT-BTC"
    )

    citations = extract_answer_citations(answer)

    assert ("Điều 144", "177/2015/TT-BTC") not in [
        (citation.article_no, citation.law_id) for citation in citations
    ]
    assert detect_unsupported_citations(answer, selected_articles) == []


def test_does_not_extract_citation_when_article_and_law_id_are_too_far_apart() -> None:
    answer = (
        "Theo Điều 16, "
        + "nội dung mô tả rất dài vượt quá giới hạn khoảng cách cho phép " * 4
        + "Nghị định 80/2021/NĐ-CP."
    )

    assert extract_answer_citations(answer) == []


def test_near_supported_citation_with_comma_is_not_flagged() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 27"}]
    answer = "Theo Điều 27, Nghị định 65/2023/NĐ-CP, thời hạn là 10 ngày."

    assert detect_unsupported_citations(answer, selected_articles) == []


def test_near_unsupported_citation_with_comma_is_flagged() -> None:
    selected_articles = [{"law_id": "65/2023/NĐ-CP", "article_no": "Điều 31"}]
    answer = "Theo Điều 27, Nghị định 65/2023/NĐ-CP, thời hạn là 10 ngày."

    unsupported = detect_unsupported_citations(answer, selected_articles)

    assert len(unsupported) == 1
    assert unsupported[0].article_no == "Điều 27"
    assert unsupported[0].law_id == "65/2023/NĐ-CP"
    assert "Lưu ý" not in unsupported[0].raw_text
    assert "Căn cứ pháp lý" not in unsupported[0].raw_text
