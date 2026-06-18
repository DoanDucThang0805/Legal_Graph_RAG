"""Citation post-processing for grounded legal answers.

This module only works with selected canonical articles passed by the caller.
It does not call LLMs, retrieval, or submission builders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


ARTICLE_NO_PATTERN = re.compile(r"\b(?:điều|Điều)\s+0*(\d+[a-zA-Z]?)\b", flags=re.IGNORECASE)


@dataclass(frozen=True)
class CitationArticle:
    """Minimal citation metadata derived from a selected article."""

    article_no: str
    law_id: str
    law_title: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.article_no.casefold(), self.law_id.casefold(), self.law_title.casefold())


def postprocess_citations(answer: str, selected_articles: list) -> str:
    """Ensure selected legal articles are mentioned in a generated answer."""

    normalized_answer = _normalize_article_mentions(str(answer or "").strip())
    if not selected_articles:
        return normalized_answer

    citation_articles = _deduplicate_articles(selected_articles)
    missing_articles = [
        article for article in citation_articles if not _answer_mentions_article(normalized_answer, article)
    ]
    if not missing_articles:
        return normalized_answer

    citation_lines = [_format_citation_line(article) for article in missing_articles]
    citation_block = "\n".join(["Căn cứ pháp lý:", *citation_lines])

    if not normalized_answer:
        return citation_block
    return f"{normalized_answer}\n\n{citation_block}"


def _normalize_article_mentions(text: str) -> str:
    """Normalize simple article references such as 'điều 04' to 'Điều 4'."""

    return ARTICLE_NO_PATTERN.sub(lambda match: f"Điều {match.group(1)}", text)


def _deduplicate_articles(selected_articles: list) -> list[CitationArticle]:
    articles: list[CitationArticle] = []
    seen: set[tuple[str, str, str]] = set()

    for item in selected_articles:
        article = _to_citation_article(item)
        if article is None or article.key in seen:
            continue
        seen.add(article.key)
        articles.append(article)

    return articles


def _to_citation_article(article: Any) -> CitationArticle | None:
    article_no = _normalize_article_mentions(_get_article_value(article, "article_no"))
    law_id = _get_article_value(article, "law_id")
    law_title = _get_article_value(article, "law_title")

    if not article_no:
        return None

    return CitationArticle(article_no=article_no, law_id=law_id, law_title=law_title)


def _answer_mentions_article(answer: str, article: CitationArticle) -> bool:
    normalized_answer = answer.casefold()
    article_no = article.article_no.casefold()
    if article_no not in normalized_answer:
        return False

    # Nếu answer đã nhắc Điều X, coi là đủ căn cứ ở mức postprocess nhẹ.
    # Prompt đã yêu cầu LLM nhắc tên/mã văn bản, còn task này chỉ append khi thiếu Điều đã chọn.
    return True


def _format_citation_line(article: CitationArticle) -> str:
    parts = [article.article_no, article.law_id, article.law_title]
    return "- " + " - ".join(part for part in parts if part)


def _get_article_value(article: Any, field_name: str) -> str:
    if isinstance(article, dict):
        value = article.get(field_name)
    else:
        value = getattr(article, field_name, None)

    if value is None:
        return ""
    return str(value).strip()
