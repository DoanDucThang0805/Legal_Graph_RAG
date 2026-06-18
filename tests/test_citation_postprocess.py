from dataclasses import dataclass

from backend.qa.citation_postprocess import postprocess_citations


def test_append_missing_citation_from_selected_article() -> None:
    answer = "Doanh nghiệp nhỏ và vừa được xác định theo tiêu chí luật định."
    articles = [
        {
            "article_no": "Điều 4",
            "law_id": "04/2017/QH14",
            "law_title": "Luật hỗ trợ doanh nghiệp nhỏ và vừa",
        }
    ]

    result = postprocess_citations(answer, articles)

    assert "Căn cứ pháp lý:" in result
    assert "- Điều 4 - 04/2017/QH14 - Luật hỗ trợ doanh nghiệp nhỏ và vừa" in result


def test_does_not_append_when_answer_already_mentions_article() -> None:
    answer = "Theo điều 04, doanh nghiệp nhỏ và vừa bao gồm doanh nghiệp siêu nhỏ."
    articles = [
        {
            "article_no": "Điều 4",
            "law_id": "04/2017/QH14",
            "law_title": "Luật hỗ trợ doanh nghiệp nhỏ và vừa",
        }
    ]

    result = postprocess_citations(answer, articles)

    assert "Theo Điều 4" in result
    assert "Căn cứ pháp lý:" not in result


def test_deduplicates_selected_articles_before_append() -> None:
    answer = "Câu trả lời chưa nhắc căn cứ."
    article = {
        "article_no": "Điều 4",
        "law_id": "04/2017/QH14",
        "law_title": "Luật hỗ trợ doanh nghiệp nhỏ và vừa",
    }

    result = postprocess_citations(answer, [article, article])

    assert result.count("- Điều 4 - 04/2017/QH14 - Luật hỗ trợ doanh nghiệp nhỏ và vừa") == 1


def test_empty_selected_articles_returns_stripped_answer() -> None:
    result = postprocess_citations("  Nội dung trả lời.  ", [])

    assert result == "Nội dung trả lời."


@dataclass
class ArticleObject:
    article_no: str
    law_id: str
    law_title: str
    article_title: str | None = None


def test_supports_object_selected_articles() -> None:
    answer = "Câu trả lời chưa nhắc căn cứ."
    article = ArticleObject(
        article_no="Điều 7",
        law_id="01/2020/QH14",
        law_title="Luật Doanh nghiệp",
    )

    result = postprocess_citations(answer, [article])

    assert "- Điều 7 - 01/2020/QH14 - Luật Doanh nghiệp" in result


def test_does_not_add_articles_outside_selected_articles() -> None:
    answer = "Câu trả lời chưa nhắc căn cứ."
    articles = [
        {
            "article_no": "Điều 4",
            "law_id": "04/2017/QH14",
            "law_title": "Luật hỗ trợ doanh nghiệp nhỏ và vừa",
        }
    ]

    result = postprocess_citations(answer, articles)

    assert "Điều 5" not in result
