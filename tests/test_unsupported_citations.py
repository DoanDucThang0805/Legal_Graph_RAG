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
        "L?u ? ??y l? th?ng tin tham kh?o d?a tr?n c?n c? ???c cung c?p.\n\n"
        "C?n c? ph?p l?:\n- ?i?u 4 - 80/2021/N?-CP"
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


def test_full_four_digit_decision_id_is_supported() -> None:
    selected_articles = [{"law_id": "1727/2007/QĐ-UBND", "article_no": "Điều 6"}]
    answer = "Theo Điều 6 của Quyết định 1727/2007/QĐ-UBND, hồ sơ bao gồm giấy tờ cần thiết."

    citations = extract_answer_citations(answer)

    assert [(citation.article_no, citation.law_id) for citation in citations] == [("Điều 6", "1727/2007/QĐ-UBND")]
    assert detect_unsupported_citations(answer, selected_articles) == []


def test_unsupported_full_four_digit_decision_id_keeps_leading_digit() -> None:
    selected_articles = [{"law_id": "1727/2007/QĐ-UBND", "article_no": "Điều 5"}]
    answer = "Theo Điều 6 của Quyết định 1727/2007/QĐ-UBND, hồ sơ bao gồm giấy tờ cần thiết."

    unsupported = detect_unsupported_citations(answer, selected_articles)

    assert len(unsupported) == 1
    assert unsupported[0].article_no == "Điều 6"
    assert unsupported[0].law_id == "1727/2007/QĐ-UBND"
    assert unsupported[0].law_id.startswith("1727/")


def test_decision_id_4688_qd_ubnd_is_supported() -> None:
    selected_articles = [{"law_id": "4688/2004/QĐ-UBND", "article_no": "Điều 3"}]
    answer = "Theo Điều 3 của Quyết định 4688/2004/QĐ-UBND, thời hạn là 05 ngày."

    assert detect_unsupported_citations(answer, selected_articles) == []
    assert extract_answer_citations(answer)[0].law_id == "4688/2004/QĐ-UBND"


def test_decision_id_1231_qd_ub_is_supported() -> None:
    selected_articles = [{"law_id": "1231/1998/QĐ-UB", "article_no": "Điều 11"}]
    answer = "Theo Điều 11 của Quyết định 1231/1998/QĐ-UB, hồ sơ nộp muộn được xử lý theo quy định."

    assert detect_unsupported_citations(answer, selected_articles) == []
    assert extract_answer_citations(answer)[0].law_id == "1231/1998/QĐ-UB"


def test_malformed_article_slash_law_id_is_not_extracted() -> None:
    selected_articles = [{"law_id": "36/2005/QH11", "article_no": "Điều 32"}]
    answer = "Điều 36/2005/QH11 quy định về hàng hóa lưu thông trong nước."

    assert extract_answer_citations(answer) == []
    assert detect_unsupported_citations(answer, selected_articles) == []


def test_valid_law_citation_is_supported() -> None:
    selected_articles = [{"law_id": "36/2005/QH11", "article_no": "Điều 92"}]
    answer = "Theo Điều 92 Luật 36/2005/QH11, thương nhân có nghĩa vụ thực hiện đúng quy định."

    assert detect_unsupported_citations(answer, selected_articles) == []


def test_valid_unsupported_law_citation_is_flagged() -> None:
    selected_articles = [{"law_id": "36/2005/QH11", "article_no": "Điều 91"}]
    answer = "Theo Điều 92 Luật 36/2005/QH11, thương nhân có nghĩa vụ thực hiện đúng quy định."

    unsupported = detect_unsupported_citations(answer, selected_articles)

    assert len(unsupported) == 1
    assert unsupported[0].article_no == "Điều 92"
    assert unsupported[0].law_id == "36/2005/QH11"
