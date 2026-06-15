from backend.knowledge_processing.normalize_text import (
    normalize_article_no,
    normalize_law_id,
    normalize_law_title,
    normalize_law_type,
    normalize_vietnamese_text,
)


def test_normalize_vietnamese_text_handles_none() -> None:
    assert normalize_vietnamese_text(None) == ""


def test_normalize_vietnamese_text_normalizes_unicode_and_whitespace() -> None:
    text = "  Lua\u0302\u0323t\u00a0  Hỗ   trợ\nDNNVV  "
    assert normalize_vietnamese_text(text) == "Luật Hỗ trợ DNNVV"


def test_normalize_article_no_removes_leading_zero_and_dot() -> None:
    assert normalize_article_no("Điều 04.") == "Điều 4"


def test_normalize_article_no_standardizes_lowercase_prefix() -> None:
    assert normalize_article_no("điều 7a") == "Điều 7a"


def test_normalize_article_no_handles_none() -> None:
    assert normalize_article_no(None) == ""


def test_normalize_article_no_preserves_unmatched_value() -> None:
    assert normalize_article_no("Khoản 1 Điều 4.") == "Khoản 1 Điều 4"


def test_normalize_law_id_strips_trailing_punctuation() -> None:
    assert normalize_law_id(" 04/2017/QH14. ") == "04/2017/QH14"


def test_normalize_law_title_combines_parts() -> None:
    assert (
        normalize_law_title(
            "Luật",
            "04/2017/QH14",
            "Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
        )
        == "Luật 04/2017/QH14 Luật Hỗ trợ doanh nghiệp nhỏ và vừa"
    )


def test_normalize_law_title_dedupes_identical_parts() -> None:
    assert normalize_law_title("Luật", "04/2017/QH14", "Luật") == "Luật 04/2017/QH14"


def test_normalize_law_title_replaces_source_prefix_casing() -> None:
    assert (
        normalize_law_title("nghi_dinh", "24/LĐ-NĐ", "Nghị Định 24/LĐ-NĐ Tổ chức các tòa án")
        == "Nghị định 24/LĐ-NĐ Tổ chức các tòa án"
    )


def test_normalize_law_title_replaces_source_prefix_with_so_marker() -> None:
    assert (
        normalize_law_title("nghi_dinh", "24/LĐ-NĐ", "Nghị Định số 24/LĐ-NĐ Tổ chức các tòa án")
        == "Nghị định 24/LĐ-NĐ Tổ chức các tòa án"
    )


def test_normalize_law_type_maps_dataset_labels() -> None:
    assert normalize_law_type("nghi_dinh") == "Nghị định"
    assert normalize_law_type("thong_tu") == "Thông tư"
    assert normalize_law_type("sac_lenh") == "Sắc lệnh"


def test_normalize_law_type_preserves_standard_vietnamese_casing() -> None:
    assert normalize_law_type("Nghị định") == "Nghị định"
    assert normalize_law_type("Nghị Định") == "Nghị định"


def test_normalize_law_type_fallback_title_cases_unknown_labels() -> None:
    assert normalize_law_type("van_ban_khac") == "Van Ban Khac"
