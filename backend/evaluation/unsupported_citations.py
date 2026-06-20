"""Detect legal citations in answers that are not supported by selected articles."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


ARTICLE_PATTERN = re.compile(r"\b(?:điều|Điều)\s+0*(\d+[a-zA-Z]?)\b", flags=re.IGNORECASE)
LAW_ID_PATTERN = re.compile(
    r"\b\d{1,3}/\d{4}/(?:QH\d*|NĐ-CP|ND-CP|TT-[A-ZĐ0-9-]+|QD-[A-ZĐ0-9-]+|QĐ-[A-ZĐ0-9-]+)\b",
    flags=re.IGNORECASE,
)
STRONG_CITATION_PATTERN = re.compile(
    r"(?P<article>(?:điều|Điều)\s+0*(?P<article_no>\d+[a-zA-Z]?))"
    r"(?P<middle>.{0,120}?)"
    r"(?P<law_id>\d{1,3}/\d{4}/(?:QH\d*|NĐ-CP|ND-CP|TT-[A-ZĐ0-9-]+|QD-[A-ZĐ0-9-]+|QĐ-[A-ZĐ0-9-]+))",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class AnswerCitation:
    """Strong citation extracted from a generated answer."""

    article_no: str
    law_id: str | None
    raw_text: str


@dataclass(frozen=True)
class UnsupportedCitation:
    """Citation that is not present in the selected article context."""

    article_no: str
    law_id: str | None
    raw_text: str
    reason: str


CitationKey = tuple[str, str]


def extract_answer_citations(answer: str) -> list[AnswerCitation]:
    """Extract strong answer citations that contain both article number and law id."""
    text = str(answer or "")
    citations: list[AnswerCitation] = []
    seen: set[tuple[str, str, str]] = set()

    for match in STRONG_CITATION_PATTERN.finditer(text):
        article_no = normalize_article_no(match.group("article_no"))
        law_id = normalize_law_id(match.group("law_id"))
        if not article_no or not law_id:
            continue

        raw_text = " ".join(match.group(0).split())
        key = (article_no.casefold(), law_id.casefold(), raw_text.casefold())
        if key in seen:
            continue
        seen.add(key)
        citations.append(AnswerCitation(article_no=article_no, law_id=law_id, raw_text=raw_text))

    return citations


def detect_unsupported_citations(answer: str, selected_articles: list[Any]) -> list[UnsupportedCitation]:
    """Return strong answer citations that are absent from selected articles."""
    supported_keys = build_supported_citation_keys(selected_articles)
    unsupported: list[UnsupportedCitation] = []

    for citation in extract_answer_citations(answer):
        if citation.law_id is None:
            continue

        key = (citation.article_no.casefold(), citation.law_id.casefold())
        if key not in supported_keys:
            unsupported.append(
                UnsupportedCitation(
                    article_no=citation.article_no,
                    law_id=citation.law_id,
                    raw_text=citation.raw_text,
                    reason="citation_not_in_selected_articles",
                )
            )

    return unsupported


def build_supported_citation_keys(selected_articles: list[Any]) -> set[CitationKey]:
    """Build normalized (article_no, law_id) keys from selected article objects."""
    keys: set[CitationKey] = set()
    for article in selected_articles or []:
        law_id, article_no = _extract_selected_law_and_article(article)
        normalized_law_id = normalize_law_id(law_id)
        normalized_article_no = normalize_article_no(article_no)
        if not normalized_law_id or not normalized_article_no:
            continue
        keys.add((normalized_article_no.casefold(), normalized_law_id.casefold()))
    return keys


def normalize_article_no(value: Any) -> str:
    """Normalize article references such as 'Điều 04' to 'Điều 4'."""
    text = str(value or "").strip()
    if not text:
        return ""

    match = ARTICLE_PATTERN.search(text)
    if match:
        return f"Điều {match.group(1)}"

    if re.fullmatch(r"0*\d+[a-zA-Z]?", text):
        return f"Điều {text.lstrip('0') or '0'}"

    return text


def normalize_law_id(value: Any) -> str:
    """Extract and normalize law id from text such as 'Nghị định 65/2023/NĐ-CP'."""
    text = str(value or "").strip()
    if not text:
        return ""

    match = LAW_ID_PATTERN.search(text)
    if not match:
        return text

    law_id = match.group(0).upper()
    law_id = law_id.replace("ND-CP", "NĐ-CP").replace("QD-", "QĐ-")
    return law_id


def format_unsupported_citation(citation: UnsupportedCitation) -> str:
    """Format unsupported citation for CSV reports."""
    law_id = citation.law_id or ""
    return f"{citation.article_no}|{law_id}|{citation.raw_text}"


def _extract_selected_law_and_article(article: Any) -> tuple[str, str]:
    if isinstance(article, str):
        return _parse_canonical_article_string(article)

    if isinstance(article, Mapping):
        law_id = _first_text(article.get("law_id"), article.get("document_id"))
        article_no = _first_text(article.get("article_no"), article.get("article_number"))
        if law_id and article_no:
            return law_id, article_no
        article_id = _first_text(article.get("article_id"), article.get("legal_article_id"))
        if article_id:
            return _parse_canonical_article_string(article_id)
        return law_id, article_no

    law_id = _first_text(getattr(article, "law_id", None), getattr(article, "document_id", None))
    article_no = _first_text(getattr(article, "article_no", None), getattr(article, "article_number", None))
    if law_id and article_no:
        return law_id, article_no

    article_id = _first_text(getattr(article, "article_id", None), getattr(article, "legal_article_id", None))
    if article_id:
        return _parse_canonical_article_string(article_id)

    return law_id, article_no


def _parse_canonical_article_string(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in str(value or "").split("|")]
    if len(parts) >= 3:
        return parts[0], parts[2]
    return "", ""


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
