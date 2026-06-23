import json

from backend.retrieval.llm_verifier import LLMVerifier


class StaticLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompt = ""

    def generate(self, prompt: str, **kwargs: object) -> str:
        self.prompt = prompt
        return self.response


class FailingLLMClient:
    def generate(self, prompt: str, **kwargs: object) -> str:
        raise RuntimeError("boom")


def test_verifier_disabled_keeps_original_article_ids() -> None:
    candidates = [{"article_id": "article-a"}, {"article_id": "article-b"}]

    result = LLMVerifier(enabled=False).verify("question", candidates)

    assert result.verifier_status == "disabled"
    assert result.verdict == "unknown"
    assert result.keep_article_ids == ["article-a", "article-b"]
    assert result.drop_article_ids == []


def test_verifier_import_and_ok_json_parse() -> None:
    client = StaticLLMClient(
        json.dumps(
            {
                "verdict": "sufficient",
                "keep_article_ids": ["article-a"],
                "drop_article_ids": ["article-b"],
                "reason": "article-a answers the question",
                "confidence": 0.82,
                "verifier_status": "ok",
            }
        )
    )
    candidates = [{"article_id": "article-a"}, {"article_id": "article-b"}]

    result = LLMVerifier(llm_client=client, enabled=True).verify("question", candidates)

    assert result.verifier_status == "ok"
    assert result.verdict == "sufficient"
    assert result.keep_article_ids == ["article-a"]
    assert result.drop_article_ids == ["article-b"]
    assert result.confidence == 0.82


def test_verifier_parse_error_keeps_original_article_ids() -> None:
    client = StaticLLMClient("not json")
    candidates = [{"article_id": "article-a"}, {"article_id": "article-b"}]

    result = LLMVerifier(llm_client=client, enabled=True).verify("question", candidates)

    assert result.verifier_status == "parse_error"
    assert result.keep_article_ids == ["article-a", "article-b"]
    assert result.drop_article_ids == []


def test_verifier_runtime_error_keeps_original_article_ids() -> None:
    candidates = [{"article_id": "article-a"}, {"article_id": "article-b"}]

    result = LLMVerifier(llm_client=FailingLLMClient(), enabled=True).verify("question", candidates)

    assert result.verifier_status == "runtime_error"
    assert result.keep_article_ids == ["article-a", "article-b"]
    assert result.drop_article_ids == []


def test_verifier_missing_fields_normalize_to_safe_defaults() -> None:
    client = StaticLLMClient('{"confidence": 2.5}')
    candidates = [{"article_id": "article-a"}, {"article_id": "article-b"}]

    result = LLMVerifier(llm_client=client, enabled=True).verify("question", candidates)

    assert result.verifier_status == "ok"
    assert result.verdict == "unknown"
    assert result.keep_article_ids == ["article-a", "article-b"]
    assert result.drop_article_ids == []
    assert result.confidence == 1.0


def test_verifier_ignores_unknown_article_ids_from_llm() -> None:
    client = StaticLLMClient(
        json.dumps(
            {
                "verdict": "partial",
                "keep_article_ids": ["article-a", "invented-article"],
                "drop_article_ids": ["article-b", "invented-article"],
                "reason": "partial evidence",
                "confidence": -1,
                "verifier_status": "ok",
            }
        )
    )
    candidates = [{"article_id": "article-a"}, {"article_id": "article-b"}]

    result = LLMVerifier(llm_client=client, enabled=True).verify("question", candidates)

    assert result.keep_article_ids == ["article-a"]
    assert result.drop_article_ids == ["article-b"]
    assert result.confidence == 0.0


def test_verifier_prompt_restricts_output_and_citations() -> None:
    client = StaticLLMClient('{"verdict":"unknown","verifier_status":"ok"}')
    candidates = [
        {
            "article_id": "article-a",
            "law_id": "01/2024/QH15",
            "law_title": "Luật mẫu",
            "article_no": "Điều 1",
            "article_text": "Nội dung căn cứ.",
        }
    ]

    LLMVerifier(llm_client=client, enabled=True).verify("question", candidates)

    assert "Không tự tạo citation mới" in client.prompt
    assert "Không sinh relevant_docs hoặc relevant_articles" in client.prompt
    assert "article-a" in client.prompt
