"""LLM-based verifier for selected retrieval candidates.

The verifier is intentionally independent from hybrid retrieval orchestration.
It only runs when called directly with an injected LLM client, and all failure
paths keep the original candidate/article ids.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)

VERIFIER_PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "verifier_prompt.txt"
VALID_VERDICTS = {"sufficient", "partial", "insufficient", "unknown"}
VALID_STATUSES = {"ok", "disabled", "parse_error", "runtime_error"}

FALLBACK_VERIFIER_PROMPT = """Bạn là verifier cho hệ thống Vietnamese Legal RAG.
Chỉ đánh giá candidates được cung cấp đối với câu hỏi.
Không tạo citation mới, không sinh relevant_docs/relevant_articles.
Chỉ trả JSON hợp lệ, không markdown.
"""


class LLMClientProtocol(Protocol):
    """Minimal protocol expected from injected LLM clients."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from a prompt."""


@dataclass(frozen=True)
class VerifierResult:
    """Safe verifier result used by downstream code."""

    verdict: str = "unknown"
    keep_article_ids: list[str] = field(default_factory=list)
    drop_article_ids: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0
    verifier_status: str = "disabled"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "verdict": self.verdict,
            "keep_article_ids": list(self.keep_article_ids),
            "drop_article_ids": list(self.drop_article_ids),
            "reason": self.reason,
            "confidence": self.confidence,
            "verifier_status": self.verifier_status,
        }


class LLMVerifier:
    """Verify whether provided candidates are sufficient for a question."""

    def __init__(
        self,
        llm_client: LLMClientProtocol | None = None,
        *,
        enabled: bool = False,
        prompt_template: str | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.enabled = enabled
        self.prompt_template = prompt_template

    def verify(
        self,
        question: str,
        candidates: list[Any],
        **generation_kwargs: Any,
    ) -> VerifierResult:
        """Verify provided candidates with safe fallback behavior.

        Args:
            question: User legal question.
            candidates: Candidate dicts/objects already produced by retrieval.
            **generation_kwargs: Extra kwargs forwarded to llm_client.generate().

        Returns:
            VerifierResult with original article ids preserved on disabled,
            parse_error, or runtime_error paths.
        """

        original_article_ids = _extract_article_ids(candidates)
        if not self.enabled:
            return _fallback_result(
                status="disabled",
                article_ids=original_article_ids,
                reason="Verifier is disabled.",
            )

        if self.llm_client is None:
            return _fallback_result(
                status="runtime_error",
                article_ids=original_article_ids,
                reason="llm_client is required when verifier is enabled.",
            )

        prompt = self.build_prompt(question=question, candidates=candidates)
        try:
            raw_output = self.llm_client.generate(prompt, **generation_kwargs)
        except Exception as exc:  # pragma: no cover - exact client errors vary.
            LOGGER.warning("LLM verifier runtime error: %s", exc)
            return _fallback_result(
                status="runtime_error",
                article_ids=original_article_ids,
                reason="LLM verifier runtime error.",
            )

        parsed = _parse_json_object(str(raw_output))
        if parsed is None:
            return _fallback_result(
                status="parse_error",
                article_ids=original_article_ids,
                reason="LLM verifier returned invalid JSON.",
            )

        return _normalize_result(parsed, original_article_ids)

    def build_prompt(self, question: str, candidates: list[Any]) -> str:
        """Build verifier prompt from already-selected retrieval candidates."""

        candidate_context = _format_candidate_context(candidates)
        template = self.prompt_template or _load_prompt_template()
        return "\n".join(
            [
                template.strip(),
                "",
                "Question:",
                str(question or "").strip(),
                "",
                "Candidates:",
                candidate_context,
                "",
                "Required JSON schema:",
                json.dumps(
                    {
                        "verdict": "sufficient|partial|insufficient|unknown",
                        "keep_article_ids": [],
                        "drop_article_ids": [],
                        "reason": "...",
                        "confidence": 0.0,
                        "verifier_status": "ok",
                    },
                    ensure_ascii=False,
                ),
            ]
        )


def _load_prompt_template() -> str:
    try:
        content = VERIFIER_PROMPT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return FALLBACK_VERIFIER_PROMPT
    return content or FALLBACK_VERIFIER_PROMPT


def _format_candidate_context(candidates: list[Any]) -> str:
    if not candidates:
        return "[]"

    compact_candidates = []
    for index, candidate in enumerate(candidates, start=1):
        compact_candidates.append(
            {
                "index": index,
                "article_id": _get_value_as_text(candidate, "article_id"),
                "law_id": _get_value_as_text(candidate, "law_id"),
                "law_title": _get_value_as_text(candidate, "law_title"),
                "article_no": _get_value_as_text(candidate, "article_no"),
                "article_title": _get_value_as_text(candidate, "article_title"),
                "text": _get_candidate_text(candidate),
            }
        )
    return json.dumps(compact_candidates, ensure_ascii=False, indent=2)


def _get_candidate_text(candidate: Any) -> str:
    for field_name in ("article_text", "text", "content", "content_text"):
        value = _get_value(candidate, field_name)
        if value:
            return _truncate_text(str(value), max_chars=1200)

    metadata = _get_value(candidate, "metadata")
    if isinstance(metadata, dict):
        for field_name in ("article_text", "text", "content", "content_text"):
            value = metadata.get(field_name)
            if value:
                return _truncate_text(str(value), max_chars=1200)

    return ""


def _extract_article_ids(candidates: list[Any]) -> list[str]:
    article_ids: list[str] = []
    for candidate in candidates:
        article_id = _get_value_as_text(candidate, "article_id")
        if article_id:
            article_ids.append(article_id)
    return article_ids


def _parse_json_object(raw_output: str) -> dict[str, Any] | None:
    text = raw_output.strip()
    if not text:
        return None

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    if not isinstance(value, dict):
        return None
    return value


def _normalize_result(parsed: dict[str, Any], original_article_ids: list[str]) -> VerifierResult:
    verdict = str(parsed.get("verdict") or "unknown").strip().lower()
    if verdict not in VALID_VERDICTS:
        verdict = "unknown"

    keep_article_ids = _normalize_article_id_list(parsed.get("keep_article_ids"), original_article_ids)
    drop_article_ids = _normalize_article_id_list(parsed.get("drop_article_ids"), original_article_ids)

    # Nếu LLM thiếu keep_article_ids, giữ toàn bộ candidates để tránh tự loại bỏ nhầm.
    if "keep_article_ids" not in parsed:
        keep_article_ids = list(original_article_ids)
        drop_article_ids = []

    keep_set = set(keep_article_ids)
    drop_article_ids = [article_id for article_id in drop_article_ids if article_id not in keep_set]

    reason = str(parsed.get("reason") or "").strip()
    confidence = _clamp_confidence(parsed.get("confidence"))
    status = str(parsed.get("verifier_status") or "ok").strip().lower()
    if status not in VALID_STATUSES or status != "ok":
        status = "ok"

    return VerifierResult(
        verdict=verdict,
        keep_article_ids=keep_article_ids,
        drop_article_ids=drop_article_ids,
        reason=reason,
        confidence=confidence,
        verifier_status=status,
    )


def _fallback_result(status: str, article_ids: list[str], reason: str) -> VerifierResult:
    return VerifierResult(
        verdict="unknown",
        keep_article_ids=list(article_ids),
        drop_article_ids=[],
        reason=reason,
        confidence=0.0,
        verifier_status=status,
    )


def _normalize_article_id_list(value: Any, allowed_article_ids: list[str]) -> list[str]:
    if not isinstance(value, list):
        return []

    allowed = set(allowed_article_ids)
    normalized: list[str] = []
    for item in value:
        article_id = str(item or "").strip()
        if article_id and article_id in allowed and article_id not in normalized:
            normalized.append(article_id)
    return normalized


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(confidence, 0.0), 1.0)


def _get_value_as_text(obj: Any, field_name: str) -> str:
    value = _get_value(obj, field_name)
    if value is None:
        return ""
    return str(value).strip()


def _get_value(obj: Any, field_name: str) -> Any:
    if isinstance(obj, dict):
        value = obj.get(field_name)
    else:
        value = getattr(obj, field_name, None)

    if value is None:
        metadata = obj.get("metadata") if isinstance(obj, dict) else getattr(obj, "metadata", None)
        if isinstance(metadata, dict):
            value = metadata.get(field_name)
    return value


def _truncate_text(text: str, *, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
