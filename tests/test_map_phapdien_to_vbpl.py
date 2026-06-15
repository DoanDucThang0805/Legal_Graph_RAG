import json

import polars as pl

from backend.knowledge_processing.map_phapdien_to_vbpl import (
    build_mapping_dataframe,
    extract_article_no_from_text,
    extract_item_id,
    extract_law_id_from_source_text,
    parse_source_link,
)


def test_extract_item_id_from_vbpl_url() -> None:
    assert extract_item_id("http://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=18562#Chuong_I_Dieu_1") == "18562"


def test_extract_article_no_from_anchor() -> None:
    assert extract_article_no_from_text("#Chuong_I_Dieu_04") == "Điều 4"


def test_extract_law_id_from_source_text() -> None:
    assert (
        extract_law_id_from_source_text(
            "(Điều 1 Luật số 32/2004/QH11 An ninh Quốc gia ngày 03/12/2004)"
        )
        == "32/2004/QH11"
    )


def test_parse_source_link_dict_json() -> None:
    value = json.dumps({"href": "http://example.test?ItemID=1#Dieu_2", "text": "Điều 2 Test"})
    parsed = parse_source_link(value)

    assert parsed.href == "http://example.test?ItemID=1#Dieu_2"
    assert parsed.text == "Điều 2 Test"


def test_build_mapping_dataframe_exact_item_and_article_no() -> None:
    phapdien_df = pl.DataFrame(
        [
            {
                "phapdien_id": "phapdien:1",
                "article_title": "Điều 1. Test",
                "content_text": "Nội dung từ pháp điển",
                "source_note_text": "",
                "source_url": "",
                "source_links_json": json.dumps(
                    {"href": "http://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=100#Chuong_I_Dieu_1"}
                ),
            }
        ]
    )
    legal_articles_df = pl.DataFrame(
        [
            {
                "article_id": "L1|Luật Test|Điều 1",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 1",
                "article_text": "Nội dung canonical",
                "source_url": "http://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=100",
            }
        ]
    )

    mapping_df, debug_df = build_mapping_dataframe(phapdien_df, legal_articles_df)

    assert mapping_df.shape == (1, 7)
    assert debug_df.is_empty()
    assert mapping_df["legal_article_id"][0] == "L1|Luật Test|Điều 1"
    assert mapping_df["mapping_method"][0] == "item_id_article_no"


def test_build_mapping_dataframe_low_confidence_debug() -> None:
    phapdien_df = pl.DataFrame(
        [
            {
                "phapdien_id": "phapdien:1",
                "article_title": "Điều 9. Missing",
                "content_text": "Không có ứng viên",
                "source_note_text": "",
                "source_url": "",
                "source_links_json": "",
            }
        ]
    )
    legal_articles_df = pl.DataFrame(
        [
            {
                "article_id": "L1|Luật Test|Điều 1",
                "law_id": "L1",
                "law_title": "Luật Test",
                "article_no": "Điều 1",
                "article_text": "Nội dung canonical",
                "source_url": "http://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=100",
            }
        ]
    )

    mapping_df, debug_df = build_mapping_dataframe(phapdien_df, legal_articles_df)

    assert mapping_df.is_empty()
    assert debug_df.shape == (1, 6)
    assert debug_df["reason"][0] == "no_candidate"


def test_build_mapping_dataframe_exact_law_id_and_article_no_from_source_text() -> None:
    phapdien_df = pl.DataFrame(
        [
            {
                "phapdien_id": "phapdien:1",
                "article_title": "Điều 1. Test",
                "content_text": "Nội dung từ pháp điển",
                "source_note_text": "",
                "source_url": "",
                "source_links_json": json.dumps(
                    {"text": "(Điều 1 Luật số 32/2004/QH11 An ninh Quốc gia ngày 03/12/2004)"}
                ),
            }
        ]
    )
    legal_articles_df = pl.DataFrame(
        [
            {
                "article_id": "32/2004/QH11|Luật 32/2004/QH11 Test|Điều 1",
                "law_id": "32/2004/QH11",
                "law_title": "Luật 32/2004/QH11 Test",
                "article_no": "Điều 1",
                "article_text": "Nội dung canonical",
                "source_url": "",
            }
        ]
    )

    mapping_df, debug_df = build_mapping_dataframe(phapdien_df, legal_articles_df)

    assert mapping_df.shape == (1, 7)
    assert debug_df.is_empty()
    assert mapping_df["legal_article_id"][0] == "32/2004/QH11|Luật 32/2004/QH11 Test|Điều 1"
    assert mapping_df["mapping_method"][0] == "law_id_article_no"
