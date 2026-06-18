"""Grounded answer generation orchestration.

This module only turns selected canonical articles into a prompt and delegates
generation to an injected LLM client. It does not retrieve articles, postprocess
citations, or build submission fields.
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.qa.answer_templates import build_answer_prompt


EMPTY_CONTEXT_FALLBACK = (
    "Chưa đủ căn cứ pháp lý được cung cấp để kết luận chắc chắn. "
    "Vui lòng bổ sung điều luật hoặc văn bản pháp lý liên quan để có thể trả lời chính xác hơn. "
    "Lưu ý: đây là thông tin tham khảo dựa trên căn cứ được cung cấp."
)


class LLMClientProtocol(Protocol):
    """Minimal protocol expected from generation clients."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from a prompt."""


class AnswerGenerator:
    """Build grounded prompts and call an injected LLM client."""

    def __init__(self, llm_client: LLMClientProtocol | None = None) -> None:
        self.llm_client = llm_client

    def generate_answer(
        self,
        question: str,
        selected_articles: list,
        answer_type: str = "general",
        **kwargs: Any,
    ) -> str:
        """Generate an answer from selected canonical articles.

        Args:
            question: User legal question.
            selected_articles: Canonical article dicts/objects already selected by retrieval.
            answer_type: Query answer type used to choose prompt guidance.
            **kwargs: Extra generation kwargs forwarded to llm_client.generate().

        Returns:
            Generated answer string, or a deterministic fallback when no legal
            articles were provided.
        """

        if not selected_articles:
            return EMPTY_CONTEXT_FALLBACK

        if self.llm_client is None:
            raise ValueError("llm_client is required when selected_articles is not empty")

        prompt = build_answer_prompt(
            question=question,
            articles=selected_articles,
            answer_type=answer_type,
        )
        answer = self.llm_client.generate(prompt, **kwargs)
        return str(answer).strip()
