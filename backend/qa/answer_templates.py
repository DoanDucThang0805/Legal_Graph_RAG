"""Prompt templates for grounded legal QA answers.

This module only builds prompts from already-selected canonical articles. It
does not call an LLM, retriever, or submission builder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "legal_qa_prompt.txt"

FALLBACK_BASE_PROMPT = """Bạn là trợ lý pháp lý AI cho doanh nghiệp tại Việt Nam.

Nguyên tắc bắt buộc:
- Chỉ dùng căn cứ pháp lý được cung cấp trong selected_articles/context.
- Không sử dụng kiến thức ngoài context.
- Không tự sinh hoặc đoán citation.
- Chỉ được viện dẫn cặp Điều + Văn bản nếu cặp đó xuất hiện trong danh sách căn cứ được phép hoặc context được cung cấp.
- Không tự suy đoán số điều, số nghị định, số thông tư, số luật hoặc mã văn bản.
- Không nêu citation yếu kiểu "theo Điều X" nếu không rõ văn bản tương ứng trong context.
- Không tự sinh relevant_docs.
- Không tự sinh relevant_articles.
- Khi trả lời phải nhắc rõ Điều X và tên/mã văn bản nếu có trong context.
- Nếu context không đủ căn cứ, phải nói rõ không đủ căn cứ pháp lý được cung cấp để kết luận chắc chắn.
"""

ANSWER_TYPE_GUIDANCE: dict[str, str] = {
    "general": (
        "Trả lời trực tiếp vào câu hỏi, sau đó nêu căn cứ pháp lý theo từng điều "
        "được cung cấp."
    ),
    "deadline": (
        "Nêu rõ thời hạn, mốc tính thời hạn, và căn cứ Điều X tương ứng. "
        "Nếu context không có thời hạn, nói rõ chưa đủ căn cứ."
    ),
    "sanction": (
        "Nêu rõ hành vi vi phạm, mức phạt, biện pháp khắc phục hậu quả nếu có, "
        "và căn cứ Điều X tương ứng."
    ),
    "procedure": (
        "Trình bày theo các bước thủ tục, cơ quan/hình thức thực hiện nếu có, "
        "và căn cứ Điều X tương ứng."
    ),
    "dossier": (
        "Liệt kê thành phần hồ sơ/tài liệu nếu context có nêu; không tự bổ sung "
        "giấy tờ ngoài context."
    ),
    "yes_no": (
        "Kết luận Có/Không/Chưa đủ căn cứ trước, sau đó giải thích ngắn gọn dựa "
        "trên Điều X được cung cấp."
    ),
}


def build_answer_prompt(
    question: str,
    articles: list,
    answer_type: str = "general",
) -> str:
    """Build a grounded legal QA prompt from selected canonical articles."""

    normalized_question = str(question or "").strip()
    allowed_citations = _format_allowed_citations(articles)
    article_context = _format_articles_context(articles)
    guidance = ANSWER_TYPE_GUIDANCE.get(answer_type, ANSWER_TYPE_GUIDANCE["general"])
    base_prompt = _load_base_prompt()

    return "\n".join(
        [
            base_prompt.strip(),
            "",
            f"Loại câu trả lời: {answer_type or 'general'}",
            f"Định hướng trả lời: {guidance}",
            "",
            "Câu hỏi:",
            normalized_question,
            "",
            "CÁC CĂN CỨ ĐƯỢC PHÉP VIỆN DẪN:",
            allowed_citations,
            "",
            "selected_articles/context:",
            article_context,
            "",
            "Yêu cầu đầu ra:",
            "- Kết luận trực tiếp trước.",
            "- Dựa hoàn toàn trên selected_articles/context ở trên.",
            "- Chỉ viện dẫn Điều + Văn bản có trong danh sách căn cứ được phép.",
            "- Nhắc rõ Điều X và tên/mã văn bản khi viện dẫn; không viết citation yếu nếu thiếu văn bản tương ứng.",
            "- Không tạo relevant_docs hoặc relevant_articles trong câu trả lời.",
            "- Không viện dẫn điều luật/văn bản không có trong context.",
            "- Nếu context không đủ căn cứ, nói rõ không đủ căn cứ trong tài liệu được cung cấp.",
            "- Kết thúc bằng lưu ý đây là thông tin tham khảo dựa trên căn cứ được cung cấp.",
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
        return (
            "[Không có căn cứ]\n"
            "Không có selected_articles được cung cấp. Nếu không đủ căn cứ, "
            "hãy nói rõ không đủ căn cứ pháp lý được cung cấp để kết luận chắc chắn."
        )

    formatted_articles = [
        _format_single_article(index=index, article=article)
        for index, article in enumerate(articles, start=1)
    ]
    return "\n\n".join(formatted_articles)


def _format_allowed_citations(articles: list) -> str:
    if not articles:
        return (
            "[Không có căn cứ được phép]\n"
            "Không được viện dẫn Điều/Văn bản cụ thể. Hãy nói rõ không đủ căn cứ pháp lý được cung cấp."
        )

    formatted_citations = [
        _format_single_allowed_citation(index=index, article=article)
        for index, article in enumerate(articles, start=1)
    ]
    return "\n\n".join(formatted_citations)


def _format_single_allowed_citation(index: int, article: Any) -> str:
    article_id = _get_article_value(article, "article_id")
    law_id = _get_article_value(article, "law_id")
    law_title = _get_article_value(article, "law_title")
    article_no = _get_article_value(article, "article_no")
    citation = _format_citation_display(
        article_no=article_no,
        law_title=law_title,
        law_id=law_id,
    )

    return "\n".join(
        [
            f"[A{index}] article_id={article_id}",
            f"     law_id={law_id}",
            f"     law_title={law_title}",
            f"     article_no={article_no}",
            f"     citation={citation}",
        ]
    )


def _format_single_article(index: int, article: Any) -> str:
    article_id = _get_article_value(article, "article_id")
    law_id = _get_article_value(article, "law_id")
    law_title = _get_article_value(article, "law_title")
    article_no = _get_article_value(article, "article_no")
    article_title = _get_article_value(article, "article_title")
    article_text = _get_article_value(article, "article_text")

    law_display = _join_non_empty([law_id, law_title], separator=" | ")
    title_display = article_title or "(không có tiêu đề điều)"

    return "\n".join(
        [
            f"[A{index}] selected_article_context",
            f"article_id: {article_id}",
            f"Văn bản: {law_display}",
            f"Điều: {article_no}",
            f"Tiêu đề điều: {title_display}",
            "Nội dung:",
            article_text,
        ]
    )


def _format_citation_display(article_no: str, law_title: str, law_id: str) -> str:
    citation_text = _join_non_empty([article_no, law_title], separator=", ")
    if not law_id:
        return citation_text
    if not citation_text:
        return law_id
    return f"{citation_text} ({law_id})"


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
