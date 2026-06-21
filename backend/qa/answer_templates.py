"""Prompt templates for grounded legal QA answers.

This module only builds prompts from already-selected canonical articles. It
does not call an LLM, retriever, or submission builder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "legal_qa_prompt.txt"
MAX_LAW_TITLE_CHARS = 80

FALLBACK_BASE_PROMPT = """Bạn là trợ lý pháp lý AI cho doanh nghiệp Việt Nam.

Luật bắt buộc:
- Chỉ dùng selected_articles/context được cung cấp.
- Chỉ viện dẫn căn cứ có trong allowed citations.
- Không tự đoán Điều/Văn bản, relevant_docs, relevant_articles.
- Nếu thiếu căn cứ, nói rõ không đủ căn cứ trong tài liệu được cung cấp.
"""

ANSWER_TYPE_GUIDANCE: dict[str, str] = {
    "general": "Trả lời trực tiếp, rồi nêu căn cứ ngắn gọn.",
    "deadline": "Nêu thời hạn/mốc tính nếu context có; nếu không, nói chưa đủ căn cứ.",
    "sanction": "Nêu hành vi, mức phạt, khắc phục nếu context có.",
    "procedure": "Trình bày bước thủ tục dựa trên context.",
    "dossier": "Liệt kê hồ sơ/tài liệu chỉ khi context nêu rõ.",
    "yes_no": "Kết luận Có/Không/Chưa đủ căn cứ, rồi giải thích ngắn.",
}


def build_answer_prompt(
    question: str,
    articles: list,
    answer_type: str = "general",
) -> str:
    """Build a compact grounded legal QA prompt from selected canonical articles."""

    normalized_question = str(question or "").strip()
    allowed_citations = _format_allowed_citations(articles)
    article_context = _format_articles_context(articles)
    guidance = ANSWER_TYPE_GUIDANCE.get(answer_type, ANSWER_TYPE_GUIDANCE["general"])
    base_prompt = _load_base_prompt()

    return "\n".join(
        [
            base_prompt.strip(),
            "",
            f"Loại: {answer_type or 'general'} | Hướng dẫn: {guidance}",
            "",
            "Câu hỏi:",
            normalized_question,
            "",
            "Allowed citations:",
            allowed_citations,
            "",
            "Context:",
            article_context,
            "",
            "Yêu cầu:",
            "- Chỉ dựa trên Context và Allowed citations.",
            "- Khi viện dẫn, chỉ dùng Điều + Văn bản trong Allowed citations; có thể nhắc [A1], [A2].",
            "- Không tự tạo relevant_docs/relevant_articles hay citation ngoài danh sách.",
            "- Nếu thiếu căn cứ, nói không đủ căn cứ trong tài liệu được cung cấp.",
            "- Kết thúc bằng lưu ý thông tin tham khảo dựa trên căn cứ được cung cấp.",
        ]
    )


def _load_base_prompt() -> str:
    """Load reusable base prompt text, with a safe fallback for imports/tests."""

    try:
        content = PROMPT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return FALLBACK_BASE_PROMPT

    return content or FALLBACK_BASE_PROMPT


def _format_articles_context(articles: list) -> str:
    if not articles:
        return "[Không có context] Không đủ căn cứ pháp lý được cung cấp."

    formatted_articles = [
        _format_single_article(index=index, article=article)
        for index, article in enumerate(articles, start=1)
    ]
    return "\n\n".join(formatted_articles)


def _format_allowed_citations(articles: list) -> str:
    if not articles:
        return "[Không có căn cứ được phép]"

    formatted_citations = [
        _format_single_allowed_citation(index=index, article=article)
        for index, article in enumerate(articles, start=1)
    ]
    return "\n".join(formatted_citations)


def _format_single_allowed_citation(index: int, article: Any) -> str:
    law_id = _get_article_value(article, "law_id")
    law_title = _shorten_law_title(_get_article_value(article, "law_title"))
    article_no = _get_article_value(article, "article_no")
    parts = _join_non_empty([article_no, law_id, law_title], separator=" | ")
    return f"[A{index}] {parts}" if parts else f"[A{index}]"


def _format_single_article(index: int, article: Any) -> str:
    article_no = _get_article_value(article, "article_no")
    article_text = _get_article_value(article, "article_text")
    label = _join_non_empty([f"[A{index}]", article_no], separator=" ")
    if not article_text:
        return f"{label}:"
    return f"{label}:\n{article_text}"


def _shorten_law_title(value: str) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= MAX_LAW_TITLE_CHARS:
        return text
    return text[: MAX_LAW_TITLE_CHARS - 3].rstrip() + "..."


def _get_article_value(article: Any, field_name: str) -> str:
    if isinstance(article, dict):
        value = article.get(field_name)
    else:
        value = getattr(article, field_name, None)

    if value is None:
        return ""
    return str(value).strip()


def _join_non_empty(values: list[str], separator: str) -> str:
    non_empty_values = [value for value in values if value]
    return separator.join(non_empty_values)
