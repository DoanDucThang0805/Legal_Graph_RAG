"""Build competition results from generated answers and canonical articles."""

from __future__ import annotations

from typing import Any


def build_submission_item(question_item: Any, answer: str, selected_articles: list) -> dict[str, Any]:
    """Build one results.json item from a question, answer, and canonical articles."""

    relevant_articles: list[str] = []
    relevant_docs: list[str] = []
    seen_articles: set[str] = set()
    seen_doc_law_ids: set[str] = set()

    for selected_article in selected_articles:
        article_id, law_id, law_title = _canonicalize_article(selected_article)
        if not article_id or article_id in seen_articles:
            continue

        seen_articles.add(article_id)
        relevant_articles.append(article_id)

        if law_id and law_id not in seen_doc_law_ids:
            seen_doc_law_ids.add(law_id)
            relevant_docs.append(_format_doc_id(law_id, law_title))

    return {
        "id": _get_value(question_item, "id"),
        "question": _get_value(question_item, "question"),
        "answer": str(answer or "").strip(),
        "relevant_docs": relevant_docs,
        "relevant_articles": relevant_articles,
    }


def build_results(items: list[Any]) -> list[dict[str, Any]]:
    """Build a results list from prepared records.

    Each record may be a dict/object with either:
    - question_item, answer, selected_articles
    - id, question, answer, selected_articles
    """

    results: list[dict[str, Any]] = []
    for item in items:
        question_item = _get_value(item, "question_item", default=None)
        if question_item is None:
            question_item = item

        results.append(
            build_submission_item(
                question_item=question_item,
                answer=_get_value(item, "answer"),
                selected_articles=_get_value(item, "selected_articles", default=[]),
            )
        )
    return results


def _canonicalize_article(article: Any) -> tuple[str, str, str]:
    if isinstance(article, str):
        return _parse_article_id(article)

    article_id = _get_value(article, "article_id")
    law_id = _get_value(article, "law_id")
    law_title = _get_value(article, "law_title")
    article_no = _get_value(article, "article_no")

    if article_id:
        parsed_law_id, parsed_law_title, _ = _split_article_id(article_id)
        return article_id, law_id or parsed_law_id, law_title or parsed_law_title

    if law_id and law_title and article_no:
        return f"{law_id}|{law_title}|{article_no}", law_id, law_title

    return "", law_id, law_title


def _parse_article_id(article_id: str) -> tuple[str, str, str]:
    law_id, law_title, _ = _split_article_id(article_id)
    return article_id.strip(), law_id, law_title


def _split_article_id(article_id: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in str(article_id or "").split("|", maxsplit=2)]
    if len(parts) != 3:
        return "", "", ""
    return parts[0], parts[1], parts[2]


def _format_doc_id(law_id: str, law_title: str) -> str:
    if law_title:
        return f"{law_id}|{law_title}"
    return law_id


def _get_value(item: Any, field_name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        value = item.get(field_name, default)
    else:
        value = getattr(item, field_name, default)

    if value is None:
        return default
    return value
