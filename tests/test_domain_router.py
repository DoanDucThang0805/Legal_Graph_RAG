from backend.query_analysis.domain_router import OTHER_DOMAIN, classify_domain


def test_classify_domain_detects_sme_support() -> None:
    result = classify_domain("Doanh nghiệp nhỏ và vừa được hỗ trợ khởi nghiệp sáng tạo như thế nào?")

    assert result.domain == "sme_support"
    assert result.confidence > 0.0
    assert "doanh nghiệp nhỏ và vừa" in result.matched_keywords


def test_classify_domain_detects_sme_support_new_company_phrase() -> None:
    result = classify_domain("Công ty nhỏ và vừa được hỗ trợ từ nhà nước như thế nào?")

    assert result.domain == "sme_support"
    assert "công ty nhỏ và vừa" in result.matched_keywords


def test_classify_domain_detects_sme_support_new_support_phrases() -> None:
    result = classify_domain("Doanh nghiệp được hỗ trợ tư vấn, hỗ trợ mặt bằng tại cơ sở ươm tạo không?")

    assert result.domain == "sme_support"
    assert "hỗ trợ tư vấn" in result.matched_keywords
    assert "hỗ trợ mặt bằng" in result.matched_keywords
    assert "cơ sở ươm tạo" in result.matched_keywords


def test_classify_domain_detects_tax_invoice() -> None:
    result = classify_domain("Công ty chậm nộp thuế và lập hóa đơn sai thì bị xử lý thế nào?")

    assert result.domain == "tax_invoice"
    assert result.confidence > 0.0
    assert result.scores["tax_invoice"] > 0.0


def test_classify_domain_detects_tax_invoice_new_phrases() -> None:
    result = classify_domain(
        "Báo cáo tình hình sử dụng hóa đơn điện tử và hóa đơn GTGT phải kê khai thuế thế nào?"
    )

    assert result.domain == "tax_invoice"
    assert "báo cáo tình hình sử dụng hóa đơn" in result.matched_keywords
    assert "hóa đơn điện tử" in result.matched_keywords
    assert "hóa đơn gtgt" in result.matched_keywords


def test_classify_domain_detects_labor_bhxh() -> None:
    result = classify_domain("Người lao động thử việc có phải đóng bảo hiểm xã hội không?")

    assert result.domain == "labor_bhxh"
    assert result.confidence > 0.0


def test_classify_domain_detects_business_registration() -> None:
    result = classify_domain("Hộ kinh doanh thay đổi người đại diện theo pháp luật cần thủ tục gì?")

    assert result.domain == "business_registration"
    assert "hộ kinh doanh" in result.matched_keywords


def test_classify_domain_detects_ip_consumer_data_new_phrases() -> None:
    result = classify_domain("Đơn đăng ký nhãn hiệu có phải nộp lệ phí duy trì chỉ dẫn địa lý không?")

    assert result.domain == "ip_consumer_data"
    assert "đơn đăng ký" in result.matched_keywords
    assert "nhãn hiệu" in result.matched_keywords
    assert "lệ phí duy trì" in result.matched_keywords
    assert "chỉ dẫn địa lý" in result.matched_keywords


def test_classify_domain_detects_accounting_new_phrases() -> None:
    result = classify_domain(
        "Quỹ khen thưởng và quỹ phúc lợi trình bày trên báo cáo tình hình tài chính thế nào?"
    )

    assert result.domain == "accounting"
    assert "quỹ khen thưởng" in result.matched_keywords
    assert "quỹ phúc lợi" in result.matched_keywords
    assert "báo cáo tình hình tài chính" in result.matched_keywords


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
