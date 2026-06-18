from backend.query_analysis.complexity_detector import MULTI_HOP, SINGLE_HOP, detect_complexity


def test_detect_complexity_defaults_to_single_hop() -> None:
    result = detect_complexity("Doanh nghiệp nhỏ và vừa được hỗ trợ những gì?")

    assert result.complexity == SINGLE_HOP
    assert result.score == 0.0
    assert result.reasons == ("no_multi_hop_signal",)


def test_detect_complexity_detects_vua_cue() -> None:
    result = detect_complexity("Doanh nghiệp vừa thay đổi địa chỉ vừa đăng ký thêm ngành nghề thì làm gì?")

    assert result.complexity == MULTI_HOP
    assert "vừa" in result.matched_cues
    assert "cue:vừa" in result.reasons


def test_detect_complexity_detects_dong_thoi_cue() -> None:
    result = detect_complexity("Công ty nộp thuế chậm, đồng thời lập hóa đơn sai thì bị xử lý thế nào?")

    assert result.complexity == MULTI_HOP
    assert "đồng thời" in result.matched_cues


def test_detect_complexity_detects_sau_do_cue() -> None:
    result = detect_complexity("Sau khi đăng ký hộ kinh doanh, sau đó muốn chuyển thành doanh nghiệp thì sao?")

    assert result.complexity == MULTI_HOP
    assert "sau đó" in result.matched_cues


def test_detect_complexity_detects_trong_khi_cue() -> None:
    result = detect_complexity("Trong khi đang thử việc, người lao động có được nghỉ không?")

    assert result.complexity == MULTI_HOP
    assert "trong khi" in result.matched_cues


def test_multiple_domain_signals_can_increase_multi_hop_score() -> None:
    result = detect_complexity(
        "Doanh nghiệp có vướng mắc về thuế và hợp đồng.",
        domain_scores={"tax_invoice": 1.2, "commerce_contract": 0.8},
    )

    assert result.complexity == SINGLE_HOP
    assert result.score > 0.0
    assert "multiple_domain_signals:2" in result.reasons


def test_multiple_domain_signals_with_cue_detects_multi_hop() -> None:
    result = detect_complexity(
        "Doanh nghiệp vừa xử lý hóa đơn vừa chấm dứt hợp đồng lao động thì làm gì?",
        domain_scores={"tax_invoice": 1.0, "labor_bhxh": 1.0},
    )

    assert result.complexity == MULTI_HOP
    assert "multiple_domain_signals:2" in result.reasons


def test_detect_complexity_handles_none_safely() -> None:
    result = detect_complexity(None)

    assert result.complexity == SINGLE_HOP
    assert result.score == 0.0
    assert result.reasons == ("empty_question",)
