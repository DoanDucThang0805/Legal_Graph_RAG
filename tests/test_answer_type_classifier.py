from backend.query_analysis.answer_type_classifier import GENERAL_ANSWER_TYPE, classify_answer_type


def test_classify_answer_type_detects_deadline() -> None:
    result = classify_answer_type("Doanh nghiệp phải nộp hồ sơ trong bao nhiêu ngày?")

    assert result.answer_type == "deadline"
    assert result.confidence > 0.0
    assert "bao nhiêu ngày" in result.matched_cues


def test_classify_answer_type_detects_amount() -> None:
    result = classify_answer_type("Mức phí đăng ký hộ kinh doanh là bao nhiêu tiền?")

    assert result.answer_type == "amount"
    assert result.confidence > 0.0


def test_classify_answer_type_detects_sanction() -> None:
    result = classify_answer_type("Công ty lập hóa đơn sai có bị phạt tiền không?")

    assert result.answer_type == "sanction"
    assert "sanction" in result.scores


def test_classify_answer_type_detects_procedure() -> None:
    result = classify_answer_type("Thủ tục đăng ký doanh nghiệp thực hiện như thế nào?")

    assert result.answer_type == "procedure"
    assert result.confidence > 0.0


def test_classify_answer_type_detects_dossier() -> None:
    result = classify_answer_type("Hồ sơ thay đổi đăng ký doanh nghiệp gồm những giấy tờ gì?")

    assert result.answer_type == "dossier"
    assert "hồ sơ" in result.matched_cues


def test_classify_answer_type_detects_conditions() -> None:
    result = classify_answer_type("Doanh nghiệp cần đáp ứng điều kiện nào để được hỗ trợ?")

    assert result.answer_type == "conditions"
    assert result.confidence > 0.0


def test_classify_answer_type_detects_obligations() -> None:
    result = classify_answer_type("Người sử dụng lao động có trách nhiệm phải thực hiện nghĩa vụ gì?")

    assert result.answer_type == "obligations"
    assert result.confidence > 0.0


def test_classify_answer_type_detects_yes_no() -> None:
    result = classify_answer_type("Doanh nghiệp có được đơn phương chấm dứt hợp đồng hay không?")

    assert result.answer_type == "yes_no"
    assert result.confidence > 0.0


def test_classify_answer_type_detects_accounting_account() -> None:
    result = classify_answer_type("Khoản chi này hạch toán vào tài khoản kế toán nào?")

    assert result.answer_type == "accounting_account"
    assert result.confidence > 0.0


def test_classify_answer_type_detects_definition() -> None:
    result = classify_answer_type("Doanh nghiệp nhỏ và vừa là gì?")

    assert result.answer_type == "definition"
    assert result.confidence > 0.0


def test_classify_answer_type_detects_multi_part() -> None:
    result = classify_answer_type("Doanh nghiệp vừa nộp thuế, đồng thời thay đổi địa chỉ thì cần làm gì?")

    assert result.answer_type == "multi_part"
    assert result.confidence > 0.0


def test_classify_answer_type_falls_back_to_general() -> None:
    result = classify_answer_type("Một câu hỏi pháp lý chưa có tín hiệu rõ.")

    assert result.answer_type == GENERAL_ANSWER_TYPE
    assert result.confidence == 0.0
    assert result.matched_cues == ()
    assert result.scores == {}


def test_classify_answer_type_handles_none_safely() -> None:
    result = classify_answer_type(None)

    assert result.answer_type == GENERAL_ANSWER_TYPE
    assert result.confidence == 0.0
