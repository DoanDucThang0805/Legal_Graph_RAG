from backend.query_analysis.domain_router import OTHER_DOMAIN, classify_domain


def test_classify_domain_detects_sme_support() -> None:
    result = classify_domain("Doanh nghiệp nhỏ và vừa được hỗ trợ khởi nghiệp sáng tạo như thế nào?")

    assert result.domain == "sme_support"
    assert result.confidence > 0.0
    assert "doanh nghiệp nhỏ và vừa" in result.matched_keywords


def test_classify_domain_detects_tax_invoice() -> None:
    result = classify_domain("Công ty chậm nộp thuế và lập hóa đơn sai thì bị xử lý thế nào?")

    assert result.domain == "tax_invoice"
    assert result.confidence > 0.0
    assert result.scores["tax_invoice"] > 0.0


def test_classify_domain_detects_labor_bhxh() -> None:
    result = classify_domain("Người lao động thử việc có phải đóng bảo hiểm xã hội không?")

    assert result.domain == "labor_bhxh"
    assert result.confidence > 0.0


def test_classify_domain_detects_business_registration() -> None:
    result = classify_domain("Hộ kinh doanh thay đổi người đại diện theo pháp luật cần thủ tục gì?")

    assert result.domain == "business_registration"
    assert "hộ kinh doanh" in result.matched_keywords


def test_classify_domain_has_other_fallback_for_unknown_question() -> None:
    result = classify_domain("Một câu hỏi không có tín hiệu pháp lý rõ ràng.")

    assert result.domain == OTHER_DOMAIN
    assert result.confidence == 0.0
    assert result.matched_keywords == ()
    assert result.scores == {}


def test_classify_domain_handles_none_safely() -> None:
    result = classify_domain(None)

    assert result.domain == OTHER_DOMAIN
    assert result.confidence == 0.0


def test_domain_router_keeps_multiple_scores_as_soft_signals() -> None:
    result = classify_domain(
        "Hợp đồng lao động có điều khoản phạt vi phạm và bồi thường thì xử lý thế nào?"
    )

    assert result.domain in {"labor_bhxh", "commerce_contract"}
    assert "labor_bhxh" in result.scores
    assert "commerce_contract" in result.scores
