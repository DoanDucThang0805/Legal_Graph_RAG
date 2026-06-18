from backend.query_analysis.legal_entity_extractor import extract_legal_entities


def test_extract_article_numbers() -> None:
    entities = extract_legal_entities("Theo Điều 04 và điều 7a của Luật này thì xử lý thế nào?")

    assert entities["article_numbers"] == ["Điều 4", "Điều 7a"]


def test_extract_legal_document_codes_and_names() -> None:
    entities = extract_legal_entities(
        "Theo Nghị định 123/2020/NĐ-CP và Thông tư 200/2014/TT-BTC thì doanh nghiệp phải làm gì?"
    )

    assert "Nghị định 123/2020/NĐ-CP" in entities["legal_documents"]
    assert "Thông tư 200/2014/TT-BTC" in entities["legal_documents"]


def test_extract_law_name() -> None:
    entities = extract_legal_entities("Luật Hỗ trợ doanh nghiệp nhỏ và vừa quy định điều kiện hỗ trợ ra sao?")

    assert entities["legal_documents"] == ["Luật Hỗ trợ doanh nghiệp nhỏ và vừa"]


def test_extract_accounting_accounts() -> None:
    entities = extract_legal_entities("Khoản chi này hạch toán vào tài khoản 642 hay TK 156?")

    assert entities["accounting_accounts"] == ["Tài khoản 642", "Tài khoản 156"]


def test_extract_dates_and_deadlines() -> None:
    entities = extract_legal_entities(
        "Từ ngày 01/07/2025, doanh nghiệp phải nộp hồ sơ trong 10 ngày làm việc."
    )

    assert entities["dates"] == ["01/07/2025"]
    assert entities["deadlines"] == ["10 ngày làm việc"]


def test_extract_money_amounts() -> None:
    entities = extract_legal_entities("Hành vi này bị phạt tiền từ 5.000.000 đồng đến 10 triệu đồng.")

    assert entities["money_amounts"] == ["5.000.000 đồng", "10 triệu đồng"]


def test_extract_legal_entities_deduplicates_values() -> None:
    entities = extract_legal_entities("Điều 4, điều 04 và tài khoản 642, TK 642.")

    assert entities["article_numbers"] == ["Điều 4"]
    assert entities["accounting_accounts"] == ["Tài khoản 642"]


def test_extract_legal_entities_handles_none_safely() -> None:
    entities = extract_legal_entities(None)

    assert entities == {
        "article_numbers": [],
        "legal_documents": [],
        "accounting_accounts": [],
        "dates": [],
        "deadlines": [],
        "money_amounts": [],
    }
