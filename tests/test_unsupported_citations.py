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
