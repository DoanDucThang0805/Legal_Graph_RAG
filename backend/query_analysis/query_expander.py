"""Rule-based query expansion for Vietnamese legal retrieval."""

from __future__ import annotations

import logging
import re
import unicodedata

LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_EXPANSIONS = 6

SYNONYM_PAIRS: tuple[tuple[str, str], ...] = (
    ("DNNVV", "doanh nghiệp nhỏ và vừa"),
    ("hóa đơn đỏ", "hóa đơn GTGT"),
    ("cho nghỉ việc", "chấm dứt hợp đồng lao động"),
    ("trả nợ trước hạn", "tất toán sớm"),
)


def expand_query(query: str | None, max_expansions: int = DEFAULT_MAX_EXPANSIONS) -> list[str]:
    """Return a small list of expanded queries while preserving the original query."""

    normalized_query = _clean_query(query)
    if not normalized_query:
        LOGGER.warning("Cannot expand empty query.")
        return []

    if max_expansions <= 0:
        return []

    expanded_queries = [normalized_query]

    for source, target in _iter_bidirectional_synonyms():
        variant = _replace_synonym(normalized_query, source, target)
        if variant != normalized_query:
            expanded_queries.append(variant)

    return _deduplicate_queries(expanded_queries)[:max_expansions]


def _iter_bidirectional_synonyms() -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for source, target in SYNONYM_PAIRS:
        pairs.append((source, target))
        pairs.append((target, source))
    return tuple(pairs)


def _replace_synonym(query: str, source: str, target: str) -> str:
    pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", re.IGNORECASE)
    replaced = pattern.sub(target, query)
    return _clean_query(replaced)


def _clean_query(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _deduplicate_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(query)
    return result
