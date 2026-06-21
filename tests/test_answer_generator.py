from backend.qa.answer_generator import AnswerGenerator
from backend.qa.answer_templates import build_answer_prompt


class CapturingLLMClient:
    def __init__(self) -> None:
        self.prompt = ""

    def generate(self, prompt: str, **kwargs: object) -> str:
        self.prompt = prompt
        return "Câu trả lời dựa trên căn cứ được cung cấp."


def test_answer_prompt_includes_compact_allowed_citation_list_from_selected_articles() -> None:
    articles = [
        {
            "article_id": "65/2023/NĐ-CP|Nghị định 65/2023/NĐ-CP|Điều 31",
            "law_id": "65/2023/NĐ-CP",
            "law_title": "Nghị định 65/2023/NĐ-CP",
            "article_no": "Điều 31",
            "article_title": "Thời hạn giải quyết",
            "article_text": "Thời hạn giải quyết là 10 ngày.",
        }
    ]

    prompt = build_answer_prompt(
        question="Thời hạn giải quyết là bao lâu?",
        articles=articles,
        answer_type="deadline",
    )

    assert "Allowed citations:" in prompt
    assert "[A1] Điều 31 | 65/2023/NĐ-CP | Nghị định 65/2023/NĐ-CP" in prompt
    assert "[A1] Điều 31:\nThời hạn giải quyết là 10 ngày." in prompt
    assert "article_id=" not in prompt
    assert "law_id=" not in prompt
    assert "citation=" not in prompt
    assert "Điều 99" not in prompt


def test_answer_generator_passes_compact_guardrail_prompt_to_llm() -> None:
    client = CapturingLLMClient()
    generator = AnswerGenerator(llm_client=client)
    articles = [
        {
            "article_id": "36/2005/QH11|Luật Thương mại|Điều 92",
            "law_id": "36/2005/QH11",
            "law_title": "Luật Thương mại",
            "article_no": "Điều 92",
            "article_text": "Thương nhân có nghĩa vụ thực hiện đúng hợp đồng.",
        }
    ]

    answer = generator.generate_answer(
        question="Thương nhân có nghĩa vụ gì?",
        selected_articles=articles,
    )

    assert answer == "Câu trả lời dựa trên căn cứ được cung cấp."
    assert "Allowed citations:" in client.prompt
    assert "[A1] Điều 92 | 36/2005/QH11 | Luật Thương mại" in client.prompt
    assert "Chỉ dựa trên Context và Allowed citations." in client.prompt
