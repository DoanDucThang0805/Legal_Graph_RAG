"""Regex-based legal entity extractor for Vietnamese legal questions."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Iterable

LOGGER = logging.getLogger(__name__)

ARTICLE_PATTERN = re.compile(r"\bđiều\s+0*(\d+[a-z]?)\b", re.IGNORECASE)
ACCOUNTING_ACCOUNT_PATTERN = re.compile(
    r"\b(?:tài\s*khoản|tk)\s*(?:số\s*)?(\d{3,4})\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"\b(?:ngày\s*)?([0-3]?\d)[/-]([01]?\d)[/-]((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
DEADLINE_PATTERN = re.compile(
    r"\b(?:trong|chậm nhất|tối đa|không quá|thời hạn)?\s*"
    r"(\d{1,3})\s*"
    r"(ngày(?:\s+làm\s+việc)?|tháng|năm|giờ)\b",
    re.IGNORECASE,
)
MONEY_AMOUNT_PATTERN = re.compile(
    r"\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?\s*"
    r"(?:đồng|vnd|triệu\s+đồng|tỷ\s+đồng)\b",
    re.IGNORECASE,
)
CODED_DOCUMENT_PATTERN = re.compile(
    r"\b((?:luật|bộ\s+luật|nghị\s+định|thông\s+tư)"
    r"(?:\s+số)?\s+\d{1,4}/\d{4}/[A-ZĐ]+(?:-[A-ZĐ]+)*)\b",
    re.IGNORECASE,
)
NAMED_LAW_PATTERN = re.compile(
    r"\b((?:luật|bộ\s+luật)\s+"
    r"(?!số\b)"
    r"[A-Za-zÀ-ỹ0-9/().,\-\s]+?)"
    r"(?=\s+(?:quy\s+định|thì|có|không|như\s+thế\s+nào|ra\s+sao)|[?.!,;:]|$)",
    re.IGNORECASE,
)


def extract_legal_entities(question: str | None) -> dict[str, list[str]]:
    """Extract query-analysis entities from a Vietnamese legal question."""

    normalized_question = _normalize_text(question)
    if not normalized_question:
        LOGGER.warning("Cannot extract legal entities from empty question.")
        return _empty_entities()

    return {
        "article_numbers": _extract_article_numbers(normalized_question),
        "legal_documents": _extract_legal_documents(normalized_question),
        "accounting_accounts": _extract_accounting_accounts(normalized_question),
        "dates": _extract_dates(normalized_question),
        "deadlines": _extract_deadlines(normalized_question),
        "money_amounts": _extract_money_amounts(normalized_question),
    }


def _extract_article_numbers(text: str) -> list[str]:
    article_numbers = [f"Điều {match.group(1)}" for match in ARTICLE_PATTERN.finditer(text)]
    return _deduplicate(article_numbers)


def _extract_legal_documents(text: str) -> list[str]:
    documents: list[str] = []
    for match in CODED_DOCUMENT_PATTERN.finditer(text):
        document = _clean_trailing_question_words(match.group(1))
        if document:
            documents.append(_capitalize_document_type(document))

    for match in NAMED_LAW_PATTERN.finditer(text):
        document = _clean_trailing_question_words(match.group(1))
        if document:
            documents.append(_capitalize_document_type(document))

    return _deduplicate(documents)


def _extract_accounting_accounts(text: str) -> list[str]:
    accounts = [f"Tài khoản {match.group(1)}" for match in ACCOUNTING_ACCOUNT_PATTERN.finditer(text)]
    return _deduplicate(accounts)


def _extract_dates(text: str) -> list[str]:
    dates = []
    for match in DATE_PATTERN.finditer(text):
        day = int(match.group(1))
        month = int(match.group(2))
        year = match.group(3)
        dates.append(f"{day:02d}/{month:02d}/{year}")
    return _deduplicate(dates)


def _extract_deadlines(text: str) -> list[str]:
    deadlines = []
    for match in DEADLINE_PATTERN.finditer(text):
        amount = int(match.group(1))
        unit = _normalize_spaces(match.group(2).casefold())
        deadlines.append(f"{amount} {unit}")
    return _deduplicate(deadlines)


def _extract_money_amounts(text: str) -> list[str]:
    amounts = [_normalize_money_amount(match.group(0)) for match in MONEY_AMOUNT_PATTERN.finditer(text)]
    return _deduplicate(amounts)


def _empty_entities() -> dict[str, list[str]]:
    return {
        "article_numbers": [],
        "legal_documents": [],
        "accounting_accounts": [],
        "dates": [],
        "deadlines": [],
        "money_amounts": [],
    }


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\u00a0", " ")
    return _normalize_spaces(normalized).strip()


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value)


def _clean_trailing_question_words(value: str) -> str:
    document = value.strip(" ,.;:?!")
    # Regex lấy phrase rộng để giữ được tên luật; cắt các cụm hỏi thường gặp
    # ở cuối để entity không nuốt sang phần câu hỏi.
    stop_patterns = (
        r"\s+thì\b.*$",
        r"\s+có\b.*$",
        r"\s+được\b.*$",
        r"\s+không\b.*$",
        r"\s+như\s+thế\s+nào\b.*$",
        r"\s+ra\s+sao\b.*$",
    )
    for pattern in stop_patterns:
        document = re.sub(pattern, "", document, flags=re.IGNORECASE).strip(" ,.;:?!")
    return document


def _capitalize_document_type(value: str) -> str:
    replacements = {
        "bộ luật": "Bộ luật",
        "luật": "Luật",
        "nghị định": "Nghị định",
        "thông tư": "Thông tư",
    }
    result = value
    for source, target in replacements.items():
        result = re.sub(rf"^{source}\b", target, result, flags=re.IGNORECASE)
    return result


def _normalize_money_amount(value: str) -> str:
    amount = _normalize_spaces(value.strip())
    return re.sub(r"\bvnd\b", "VND", amount, flags=re.IGNORECASE)


def _deduplicate(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _normalize_spaces(value).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result
