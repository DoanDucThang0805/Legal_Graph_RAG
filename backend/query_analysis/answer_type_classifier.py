"""Rule-based answer type classifier for Vietnamese legal questions."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

GENERAL_ANSWER_TYPE = "general"


@dataclass(frozen=True)
class AnswerTypeClassification:
    """Soft answer-type signal used to tune retrieval and answer formatting."""

    answer_type: str
    confidence: float
    matched_cues: tuple[str, ...]
    scores: dict[str, float]


ANSWER_TYPE_CUES: dict[str, tuple[str, ...]] = {
    "deadline": (
        "bao lâu",
        "thời hạn",
        "chậm nhất",
        "khi nào",
        "trong bao nhiêu ngày",
        "bao nhiêu ngày",
        "bao nhiêu tháng",
        "thời điểm",
    ),
    "amount": (
        "bao nhiêu tiền",
        "mức tiền",
        "số tiền",
        "mức phí",
        "lệ phí",
        "phí",
        "tỷ lệ",
        "mức đóng",
        "mức hỗ trợ",
    ),
    "sanction": (
        "bị phạt",
        "xử phạt",
        "mức phạt",
        "phạt tiền",
        "khắc phục hậu quả",
        "biện pháp khắc phục",
        "vi phạm hành chính",
        "chế tài",
    ),
    "procedure": (
        "thủ tục",
        "đăng ký",
        "nộp",
        "gửi",
        "thực hiện như thế nào",
        "làm như thế nào",
        "quy trình",
        "trình tự",
        "cấp giấy",
    ),
    "dossier": (
        "hồ sơ",
        "giấy tờ",
        "tài liệu",
        "thành phần hồ sơ",
        "mẫu đơn",
        "đơn đề nghị",
    ),
    "conditions": (
        "điều kiện",
        "đáp ứng",
        "trường hợp nào",
        "khi nào được",
        "cần đáp ứng",
        "tiêu chí",
        "yêu cầu để",
    ),
    "obligations": (
        "nghĩa vụ",
        "trách nhiệm",
        "phải làm gì",
        "phải thực hiện",
        "có trách nhiệm",
        "bắt buộc",
        "phải bảo đảm",
    ),
    "yes_no": (
        "có được",
        "có bị",
        "có phải",
        "được phép không",
        "có cần",
        "có bắt buộc",
        "hay không",
        "không?",
    ),
    "accounting_account": (
        "tài khoản kế toán",
        "tài khoản",
        "hạch toán",
        "ghi nhận",
        "sổ kế toán",
        "báo cáo tài chính",
        "chứng từ kế toán",
        "nguyên giá",
    ),
    "definition": (
        "là gì",
        "được hiểu như thế nào",
        "khái niệm",
        "định nghĩa",
        "giải thích từ ngữ",
        "thế nào là",
    ),
    "multi_part": (
        "vừa",
        "đồng thời",
        "sau đó",
        "trong khi",
        "ngoài ra",
        "cùng lúc",
        "một mặt",
        "mặt khác",
    ),
}

PRIORITY_ORDER: tuple[str, ...] = (
    "sanction",
    "accounting_account",
    "deadline",
    "dossier",
    "procedure",
    "conditions",
    "obligations",
    "yes_no",
    "amount",
    "definition",
    "multi_part",
)


def classify_answer_type(question: str | None) -> AnswerTypeClassification:
    """Classify the expected answer style for a legal question."""

    normalized_question = _normalize_query(question)
    if not normalized_question:
        LOGGER.warning("Cannot classify empty question; falling back to %s.", GENERAL_ANSWER_TYPE)
        return AnswerTypeClassification(
            answer_type=GENERAL_ANSWER_TYPE,
            confidence=0.0,
            matched_cues=(),
            scores={},
        )

    type_matches = _score_answer_types(normalized_question)
    if not type_matches:
        return AnswerTypeClassification(
            answer_type=GENERAL_ANSWER_TYPE,
            confidence=0.0,
            matched_cues=(),
            scores={},
        )

    sorted_types = sorted(
        type_matches.items(),
        key=lambda item: (
            item[1]["score"],
            -PRIORITY_ORDER.index(item[0]) if item[0] in PRIORITY_ORDER else -len(PRIORITY_ORDER),
        ),
        reverse=True,
    )
    best_type, best_payload = sorted_types[0]
    total_score = sum(payload["score"] for payload in type_matches.values())

    return AnswerTypeClassification(
        answer_type=best_type,
        confidence=_calculate_confidence(best_payload["score"], total_score),
        matched_cues=tuple(best_payload["cues"]),
        scores={answer_type: round(payload["score"], 4) for answer_type, payload in type_matches.items()},
    )


def _score_answer_types(question: str) -> dict[str, dict[str, float | list[str]]]:
    type_matches: dict[str, dict[str, float | list[str]]] = {}

    for answer_type, cues in ANSWER_TYPE_CUES.items():
        matched_cues: list[str] = []
        score = 0.0

        for cue in cues:
            normalized_cue = _normalize_query(cue)
            if _contains_cue(question, normalized_cue):
                matched_cues.append(cue)
                score += _cue_weight(normalized_cue)

        if matched_cues:
            # Thêm điểm nhẹ cho nhiều cue cùng loại để tăng ổn định,
            # nhưng không để số lượng cue ngắn lấn át cue dài/cụ thể.
            score += min(len(matched_cues) * 0.1, 0.5)
            type_matches[answer_type] = {"score": score, "cues": matched_cues}

    return type_matches


def _normalize_query(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\u00a0", " ").casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_cue(question: str, cue: str) -> bool:
    if not cue:
        return False
    if " " in cue:
        return cue in question
    return re.search(rf"(?<!\w){re.escape(cue)}(?!\w)", question) is not None


def _cue_weight(cue: str) -> float:
    token_count = len(cue.split())
    if token_count >= 4:
        return 3.0
    if token_count >= 2:
        return 2.0
    return 1.0


def _calculate_confidence(best_score: float, total_score: float) -> float:
    if total_score <= 0.0:
        return 0.0
    return round(min(best_score / total_score, 1.0), 4)
