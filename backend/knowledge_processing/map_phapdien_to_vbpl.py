"""Map phapdien retrieval rows to canonical VBPL legal articles."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
from rapidfuzz import fuzz

from backend.config.settings import get_settings
from backend.knowledge_processing.hf_loader import save_parquet
from backend.knowledge_processing.normalize_text import (
    normalize_article_no,
    normalize_vietnamese_text,
)

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    "phapdien_id",
    "legal_article_id",
    "law_id",
    "law_title",
    "article_no",
    "mapping_score",
    "mapping_method",
]

DEBUG_COLUMNS = [
    "phapdien_id",
    "article_title",
    "source_links_json",
    "best_legal_article_id",
    "best_score",
    "reason",
]

ITEM_ID_PATTERN = re.compile(r"[?&]ItemID=(?P<item_id>\d+)", re.IGNORECASE)
ANCHOR_ARTICLE_PATTERN = re.compile(r"(?:Dieu|Điều|dieu)[_\-\s]*(?P<number>\d+[a-zA-Z]?)", re.IGNORECASE)
TEXT_ARTICLE_PATTERN = re.compile(r"(?:Điều|điều|Dieu|dieu)\s+0*(?P<number>\d+[a-zA-Z]?)", re.IGNORECASE)
LAW_ID_IN_SOURCE_TEXT_PATTERN = re.compile(
    r"(?:số|so)\s+(?P<law_id>[0-9A-Za-zĐđ][0-9A-Za-zĐđ/\-\.]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ArticleRecord:
    article_id: str
    law_id: str
    law_title: str
    article_no: str
    article_text: str
    source_url: str


@dataclass(frozen=True)
class PhapdienSourceLink:
    href: str
    text: str


def build_phapdien_to_vbpl_map(
    phapdien_path: str | Path | None = None,
    legal_articles_path: str | Path | None = None,
    output_path: str | Path | None = None,
    min_mapping_score: float = 60.0,
) -> pl.DataFrame:
    """Build phapdien-to-canonical-article mapping parquet."""

    settings = get_settings()
    processed_dir = settings.paths.processed_dir
    phapdien_source = (
        Path(phapdien_path)
        if phapdien_path is not None
        else processed_dir / "phapdien_articles.parquet"
    )
    legal_source = (
        Path(legal_articles_path)
        if legal_articles_path is not None
        else processed_dir / "legal_articles.parquet"
    )
    target_path = (
        Path(output_path)
        if output_path is not None
        else processed_dir / "phapdien_to_vbpl_map.parquet"
    )

    phapdien_df = pl.read_parquet(phapdien_source)
    legal_articles_df = pl.read_parquet(legal_source)
    mapping_df, debug_df = build_mapping_dataframe(
        phapdien_df,
        legal_articles_df,
        min_mapping_score=min_mapping_score,
    )

    save_parquet(mapping_df, target_path)
    if not debug_df.is_empty():
        debug_path = target_path.with_name(f"{target_path.stem}_low_confidence.parquet")
        save_parquet(debug_df, debug_path)
        logger.warning("Low-confidence phapdien mappings written: path=%s rows=%s", debug_path, debug_df.height)

    logger.info("Built phapdien to VBPL map: rows=%s output=%s", mapping_df.height, target_path)
    return mapping_df


def build_mapping_dataframe(
    phapdien_df: pl.DataFrame,
    legal_articles_df: pl.DataFrame,
    min_mapping_score: float = 60.0,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return accepted mappings and low-confidence debug rows."""

    article_index = _build_article_index(legal_articles_df)
    mapping_rows: list[dict[str, Any]] = []
    debug_rows: list[dict[str, Any]] = []

    for row in phapdien_df.iter_rows(named=True):
        result = _map_phapdien_row(row, article_index)
        if result and result["mapping_score"] >= min_mapping_score:
            mapping_rows.append(result)
            continue

        debug_rows.append(
            _build_debug_row(
                row,
                best_legal_article_id=result["legal_article_id"] if result else "",
                best_score=float(result["mapping_score"]) if result else 0.0,
                reason="below_threshold" if result else "no_candidate",
            )
        )

    mapping_df = _rows_to_dataframe(mapping_rows, OUTPUT_COLUMNS)
    debug_df = _rows_to_dataframe(debug_rows, DEBUG_COLUMNS)
    return mapping_df, debug_df


def _build_article_index(legal_articles_df: pl.DataFrame) -> dict[str, Any]:
    by_item_and_article: dict[tuple[str, str], ArticleRecord] = {}
    by_item: dict[str, list[ArticleRecord]] = {}
    by_law_and_article: dict[tuple[str, str], ArticleRecord] = {}

    for row in legal_articles_df.iter_rows(named=True):
        record = ArticleRecord(
            article_id=normalize_vietnamese_text(row.get("article_id")),
            law_id=normalize_vietnamese_text(row.get("law_id")),
            law_title=normalize_vietnamese_text(row.get("law_title")),
            article_no=normalize_article_no(row.get("article_no")),
            article_text=normalize_vietnamese_text(row.get("article_text")),
            source_url=normalize_vietnamese_text(row.get("source_url")),
        )
        if not record.article_id or not record.article_no:
            continue

        by_law_and_article.setdefault((record.law_id, record.article_no), record)

        item_id = extract_item_id(record.source_url)
        if not item_id:
            continue

        by_item.setdefault(item_id, []).append(record)
        by_item_and_article.setdefault((item_id, record.article_no), record)

    return {
        "by_item": by_item,
        "by_item_and_article": by_item_and_article,
        "by_law_and_article": by_law_and_article,
    }


def _map_phapdien_row(row: dict[str, Any], article_index: dict[str, Any]) -> dict[str, Any] | None:
    source_link = parse_source_link(row.get("source_links_json"))
    item_id = extract_item_id(source_link.href) or extract_item_id(row.get("source_url"))
    article_no = (
        extract_article_no_from_text(source_link.href)
        or extract_article_no_from_text(source_link.text)
        or extract_article_no_from_text(row.get("article_title"))
        or extract_article_no_from_text(row.get("source_note_text"))
    )

    if article_no:
        exact_record = article_index["by_item_and_article"].get((item_id, article_no))
        if exact_record:
            return _mapping_row(row, exact_record, 100.0, "item_id_article_no")

    law_id = (
        extract_law_id_from_source_text(source_link.text)
        or extract_law_id_from_source_text(row.get("source_note_text"))
        or extract_law_id_from_source_text(row.get("article_title"))
    )
    if law_id and article_no:
        law_record = article_index["by_law_and_article"].get((law_id, article_no))
        if law_record:
            return _mapping_row(row, law_record, 95.0, "law_id_article_no")

    if not item_id:
        return None

    candidates: list[ArticleRecord] = article_index["by_item"].get(item_id, [])
    if not candidates:
        return None

    best_record, best_score = _best_fuzzy_candidate(row, source_link, candidates)
    if best_record is None:
        return None

    method = "item_id_fuzzy_text"
    if article_no and best_record.article_no == article_no:
        method = "item_id_article_no_fuzzy_text"
    return _mapping_row(row, best_record, best_score, method)


def parse_source_link(value: Any) -> PhapdienSourceLink:
    """Parse phapdien source_links_json without treating it as official citation."""

    raw = normalize_vietnamese_text(value)
    if not raw:
        return PhapdienSourceLink(href="", text="")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return PhapdienSourceLink(href="", text=raw)

    if isinstance(parsed, dict):
        return PhapdienSourceLink(
            href=normalize_vietnamese_text(parsed.get("href")),
            text=normalize_vietnamese_text(parsed.get("text")),
        )

    if isinstance(parsed, list) and parsed:
        first_item = parsed[0]
        if isinstance(first_item, dict):
            return PhapdienSourceLink(
                href=normalize_vietnamese_text(first_item.get("href")),
                text=normalize_vietnamese_text(first_item.get("text")),
            )

    return PhapdienSourceLink(href="", text=raw)


def extract_item_id(value: Any) -> str:
    text = normalize_vietnamese_text(value)
    match = ITEM_ID_PATTERN.search(text)
    return match.group("item_id") if match else ""


def extract_article_no_from_text(value: Any) -> str:
    text = normalize_vietnamese_text(value)
    if not text:
        return ""

    match = ANCHOR_ARTICLE_PATTERN.search(text) or TEXT_ARTICLE_PATTERN.search(text)
    if not match:
        return ""
    return normalize_article_no(f"Điều {match.group('number')}")


def extract_law_id_from_source_text(value: Any) -> str:
    text = normalize_vietnamese_text(value)
    if not text:
        return ""

    match = LAW_ID_IN_SOURCE_TEXT_PATTERN.search(text)
    if not match:
        return ""

    law_id = match.group("law_id").rstrip(").,;:")
    return normalize_vietnamese_text(law_id)


def _best_fuzzy_candidate(
    row: dict[str, Any],
    source_link: PhapdienSourceLink,
    candidates: list[ArticleRecord],
) -> tuple[ArticleRecord | None, float]:
    query_text = normalize_vietnamese_text(
        " ".join(
            part
            for part in [
                source_link.text,
                row.get("article_title"),
                row.get("content_text"),
            ]
            if part
        )
    )
    if not query_text:
        return None, 0.0

    best_record: ArticleRecord | None = None
    best_score = 0.0
    for candidate in candidates:
        candidate_text = normalize_vietnamese_text(
            f"{candidate.law_title} {candidate.article_no} {candidate.article_text[:1200]}"
        )
        score = float(fuzz.token_set_ratio(query_text[:1200], candidate_text))
        if score > best_score:
            best_score = score
            best_record = candidate

    return best_record, best_score


def _mapping_row(
    phapdien_row: dict[str, Any],
    article: ArticleRecord,
    score: float,
    method: str,
) -> dict[str, Any]:
    return {
        "phapdien_id": normalize_vietnamese_text(phapdien_row.get("phapdien_id")),
        "legal_article_id": article.article_id,
        "law_id": article.law_id,
        "law_title": article.law_title,
        "article_no": article.article_no,
        "mapping_score": float(score),
        "mapping_method": method,
    }


def _build_debug_row(
    phapdien_row: dict[str, Any],
    best_legal_article_id: str,
    best_score: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "phapdien_id": normalize_vietnamese_text(phapdien_row.get("phapdien_id")),
        "article_title": normalize_vietnamese_text(phapdien_row.get("article_title")),
        "source_links_json": normalize_vietnamese_text(phapdien_row.get("source_links_json")),
        "best_legal_article_id": best_legal_article_id,
        "best_score": float(best_score),
        "reason": reason,
    }


def _rows_to_dataframe(rows: list[dict[str, Any]], columns: list[str]) -> pl.DataFrame:
    if not rows:
        schema = {
            column: pl.Float64 if column in {"mapping_score", "best_score"} else pl.Utf8
            for column in columns
        }
        return pl.DataFrame(schema=schema)
    return pl.DataFrame(rows).select(columns)
