"""Rule-based domain router for Vietnamese legal questions."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

OTHER_DOMAIN = "other"


@dataclass(frozen=True)
class DomainClassification:
    """Soft domain signal used for retrieval boosting, not hard filtering."""

    domain: str
    confidence: float
    matched_keywords: tuple[str, ...]
    scores: dict[str, float]


DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sme_support": (
        "doanh nghiệp nhỏ và vừa",
        "doanh nghiệp nhỏ",
        "doanh nghiệp vừa",
        "dnnvv",
        "sme",
        "khởi nghiệp sáng tạo",
        "chuỗi giá trị",
        "cụm liên kết ngành",
        "khu làm việc chung",
        "ươm tạo",
        "hỗ trợ doanh nghiệp",
    ),
    "tax_invoice": (
        "thuế",
        "hóa đơn",
        "chứng từ",
        "biên lai",
        "mã số thuế",
        "khai thuế",
        "nộp thuế",
        "ấn định thuế",
        "cưỡng chế",
        "lệ phí môn bài",
    ),
    "labor_bhxh": (
        "lao động",
        "người lao động",
        "nhân viên",
        "hợp đồng lao động",
        "tiền lương",
        "thử việc",
        "làm thêm",
        "bhxh",
        "bảo hiểm xã hội",
        "công đoàn",
        "an toàn vệ sinh lao động",
    ),
    "accounting": (
        "kế toán",
        "báo cáo tài chính",
        "sổ kế toán",
        "chứng từ kế toán",
        "tài khoản",
        "hạch toán",
        "giá gốc",
        "nguyên giá",
        "dự phòng",
    ),
    "ip_consumer_data": (
        "sở hữu trí tuệ",
        "sở hữu công nghiệp",
        "nhãn hiệu",
        "sáng chế",
        "kiểu dáng",
        "quyền tác giả",
        "bản ghi âm",
        "bản ghi hình",
        "người tiêu dùng",
        "dữ liệu khách hàng",
        "bảo hành",
        "dữ liệu cá nhân",
    ),
    "business_registration": (
        "đăng ký doanh nghiệp",
        "hộ kinh doanh",
        "giấy chứng nhận đăng ký",
        "cơ quan đăng ký kinh doanh",
        "người đại diện theo pháp luật",
        "vốn điều lệ",
        "chủ sở hữu hưởng lợi",
    ),
    "commerce_contract": (
        "hợp đồng",
        "thương mại",
        "đại lý",
        "nhượng quyền",
        "hội chợ",
        "triển lãm",
        "đấu thầu",
        "phạt vi phạm",
        "bồi thường",
        "giao hàng",
    ),
    "credit_guarantee": (
        "bảo lãnh tín dụng",
        "quỹ bảo lãnh tín dụng",
        "chứng thư bảo lãnh",
        "bên bảo lãnh",
    ),
}


def classify_domain(question: str | None) -> DomainClassification:
    """Classify a question into a soft legal domain.

    Domain routing is intentionally rule-based in Phase 3 and must only be used
    as a boost signal by later retrieval steps. It must not remove candidates
    from other domains.
    """

    normalized_question = _normalize_query(question)
    if not normalized_question:
        LOGGER.warning("Cannot classify empty question; falling back to %s.", OTHER_DOMAIN)
        return DomainClassification(
            domain=OTHER_DOMAIN,
            confidence=0.0,
            matched_keywords=(),
            scores={},
        )

    domain_matches = _score_domains(normalized_question)
    if not domain_matches:
        return DomainClassification(
            domain=OTHER_DOMAIN,
            confidence=0.0,
            matched_keywords=(),
            scores={},
        )

    sorted_domains = sorted(
        domain_matches.items(),
        key=lambda item: (item[1]["score"], item[1]["longest_keyword_length"]),
        reverse=True,
    )
    best_domain, best_payload = sorted_domains[0]
    total_score = sum(payload["score"] for payload in domain_matches.values())
    confidence = _calculate_confidence(best_payload["score"], total_score)

    return DomainClassification(
        domain=best_domain,
        confidence=confidence,
        matched_keywords=tuple(best_payload["keywords"]),
        scores={domain: round(payload["score"], 4) for domain, payload in domain_matches.items()},
    )


def _score_domains(question: str) -> dict[str, dict[str, float | list[str]]]:
    domain_matches: dict[str, dict[str, float | list[str]]] = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        matched_keywords: list[str] = []
        score = 0.0
        longest_keyword_length = 0

        for keyword in keywords:
            normalized_keyword = _normalize_query(keyword)
            if _contains_keyword(question, normalized_keyword):
                matched_keywords.append(keyword)
                longest_keyword_length = max(longest_keyword_length, len(normalized_keyword))
                score += _keyword_weight(normalized_keyword)

        if matched_keywords:
            # Cộng nhẹ theo số keyword để câu hỏi nhiều tín hiệu được ưu tiên,
            # nhưng vẫn giữ keyword dài/cụ thể là nguồn điểm chính.
            score += min(len(matched_keywords) * 0.15, 0.75)
            domain_matches[domain] = {
                "score": score,
                "keywords": matched_keywords,
                "longest_keyword_length": float(longest_keyword_length),
            }

    return domain_matches


def _normalize_query(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\u00a0", " ").casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_keyword(question: str, keyword: str) -> bool:
    if not keyword:
        return False

    # Keyword có dấu cách là phrase pháp lý; tìm phrase trực tiếp sau normalize.
    if " " in keyword:
        return keyword in question

    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", question) is not None


def _keyword_weight(keyword: str) -> float:
    token_count = len(keyword.split())
    if token_count >= 4:
        return 3.0
    if token_count >= 2:
        return 2.0
    return 1.0


def _calculate_confidence(best_score: float, total_score: float) -> float:
    if total_score <= 0.0:
        return 0.0
    return round(min(best_score / total_score, 1.0), 4)
