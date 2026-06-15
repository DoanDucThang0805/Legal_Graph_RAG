"""Helpers for normalizing canonical legal document records."""

from __future__ import annotations

from typing import Any

from backend.knowledge_processing.normalize_text import (
    normalize_law_id,
    normalize_law_title,
    normalize_law_type,
    normalize_vietnamese_text,
)


def normalize_legal_document_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow-normalized copy of a legal document record."""

    normalized = dict(record)
    normalized["law_id"] = normalize_law_id(record.get("law_id"))
    normalized["law_type"] = normalize_law_type(record.get("law_type"))
    normalized["law_title"] = normalize_law_title(
        record.get("law_type"),
        record.get("law_id"),
        record.get("law_title") or record.get("title"),
    )
    normalized["markdown"] = normalize_vietnamese_text(
        record.get("markdown") or record.get("body") or record.get("text")
    )
    normalized["source_url"] = normalize_vietnamese_text(record.get("source_url"))
    return normalized
