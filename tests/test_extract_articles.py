import polars as pl

from backend.knowledge_processing.extract_articles import (
    build_article_id,
    extract_articles_from_documents,
)


def test_build_article_id() -> None:
    assert (
        build_article_id("04/2017/QH14", "Luật 04/2017/QH14 Test", "Điều 4")
        == "04/2017/QH14|Luật 04/2017/QH14 Test|Điều 4"
    )


def test_extract_articles_from_documents_basic() -> None:
    documents_df = pl.DataFrame(
        [
            {
                "doc_id": "doc-1",
                "law_id": "04/2017/QH14",
                "law_title": "Luật 04/2017/QH14 Test",
                "source_url": "https://example.test",
                "legal_area": "business",
                "status": "active",
                "markdown": (
                    "### Điều 01. Phạm vi điều chỉnh "
                    "Luật này quy định nội dung thứ nhất. "
                    "### Điều 2. Đối tượng áp dụng "
                    "Luật này áp dụng cho tổ chức, cá nhân."
                ),
            }
        ]
    )

    articles = extract_articles_from_documents(documents_df)

    assert len(articles) == 2
    assert articles[0].article_no == "Điều 1"
    assert articles[0].article_id == "04/2017/QH14|Luật 04/2017/QH14 Test|Điều 1"
    assert articles[0].article_text.startswith("Điều 01. Phạm vi điều chỉnh")
    assert articles[1].article_no == "Điều 2"


def test_extract_articles_from_documents_skips_duplicate_article_id() -> None:
    documents_df = pl.DataFrame(
        [
            {
                "doc_id": "doc-1",
                "law_id": "04/2017/QH14",
                "law_title": "Luật 04/2017/QH14 Test",
                "source_url": "",
                "legal_area": "",
                "status": "",
                "markdown": "Điều 1. Nội dung điều luật đủ dài để được giữ lại.",
            },
            {
                "doc_id": "doc-2",
                "law_id": "04/2017/QH14",
                "law_title": "Luật 04/2017/QH14 Test",
                "source_url": "",
                "legal_area": "",
                "status": "",
                "markdown": "Điều 1. Nội dung trùng id nên bị bỏ qua.",
            },
        ]
    )

    articles = extract_articles_from_documents(documents_df)

    assert len(articles) == 1
    assert articles[0].article_id == "04/2017/QH14|Luật 04/2017/QH14 Test|Điều 1"
