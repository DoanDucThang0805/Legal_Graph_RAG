from backend.query_analysis.query_expander import expand_query


def test_expand_query_preserves_original_query_first() -> None:
    query = "DNNVV được hỗ trợ như thế nào?"

    expanded = expand_query(query)

    assert expanded[0] == query


def test_expand_query_expands_dnnvv_to_full_phrase() -> None:
    expanded = expand_query("DNNVV được hỗ trợ khởi nghiệp không?")

    assert "doanh nghiệp nhỏ và vừa được hỗ trợ khởi nghiệp không?" in expanded


def test_expand_query_expands_full_phrase_to_dnnvv() -> None:
    expanded = expand_query("Doanh nghiệp nhỏ và vừa được hỗ trợ gì?")

    assert "DNNVV được hỗ trợ gì?" in expanded


def test_expand_query_expands_hoa_don_do_to_gtgt() -> None:
    expanded = expand_query("Doanh nghiệp xuất hóa đơn đỏ sai thì sao?")

    assert "Doanh nghiệp xuất hóa đơn GTGT sai thì sao?" in expanded


def test_expand_query_expands_hoa_don_gtgt_to_hoa_don_do() -> None:
    expanded = expand_query("Hóa đơn GTGT bị sai mã số thuế thì xử lý thế nào?")

    assert "hóa đơn đỏ bị sai mã số thuế thì xử lý thế nào?" in expanded


def test_expand_query_expands_cho_nghi_viec_to_cham_dut_hop_dong() -> None:
    expanded = expand_query("Công ty cho nghỉ việc người lao động có cần báo trước không?")

    assert "Công ty chấm dứt hợp đồng lao động người lao động có cần báo trước không?" in expanded


def test_expand_query_expands_tra_no_truoc_han_to_tat_toan_som() -> None:
    expanded = expand_query("Doanh nghiệp trả nợ trước hạn có bị tính phí không?")

    assert "Doanh nghiệp tất toán sớm có bị tính phí không?" in expanded


def test_expand_query_deduplicates_and_limits_results() -> None:
    expanded = expand_query(
        "DNNVV xuất hóa đơn đỏ và trả nợ trước hạn",
        max_expansions=3,
    )

    assert len(expanded) == 3
    assert len(expanded) == len(set(query.casefold() for query in expanded))


def test_expand_query_handles_empty_query() -> None:
    assert expand_query(None) == []
    assert expand_query("   ") == []


def test_expand_query_respects_zero_max_expansions() -> None:
    assert expand_query("DNNVV được hỗ trợ không?", max_expansions=0) == []
