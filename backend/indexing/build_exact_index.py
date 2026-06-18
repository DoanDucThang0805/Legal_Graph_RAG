"""Build exact lookup index from canonical legal articles."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import polars as pl

from backend.config.settings import get_settings
from backend.knowledge_processing.normalize_text import normalize_article_no, normalize_vietnamese_text

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "article_id",
    "law_id",
    "law_title",
    "article_no",
    "article_title",
    "article_text",
    "source_url",
    "domain",
    "status",
]

ACCOUNTING_ACCOUNT_PATTERN = re.compile(
    r"(?:tài khoản|tai khoan|TK|account)\s*(?P<account>\d{3,4})",
    re.IGNORECASE,
)
DEADLINE_NUMBER_PATTERN = re.compile(
    r"(?P<number>\d+)\s*(?:ngày|ngay|tháng|thang|năm|nam|giờ|gio|tuần|tuan|working days|days)",
    re.IGNORECASE,
)
SANCTION_AMOUNT_PATTERN = re.compile(
    r"(?P<amount>\d+(?:[\.,]\d+)*)\s*(?:đồng|dong|triệu đồng|trieu dong|tỷ đồng|ty dong|VND)",
    re.IGNORECASE,
)
SANCTION_KEYWORDS = [
    "phạt tiền",
    "phat tien",
    "xử phạt",
    "xu phat",
    "vi phạm hành chính",
    "vi pham hanh chinh",
    "khắc phục hậu quả",
    "khac phuc hau qua",
    "đình chỉ",
    "dinh chi",
    "tước quyền sử dụng",
    "tuoc quyen su dung",
]


def build_exact_index(
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build and save exact lookup index from legal_articles.parquet."""

    settings = get_settings()
    source_path = (
        Path(input_path)
        if input_path is not None
        else settings.paths.processed_dir / "legal_articles.parquet"
    )
    target_path = (
        Path(output_path)
        if output_path is not None
        else settings.paths.processed_dir / "exact_index.json"
    )

    df = _read_legal_articles(source_path)
    index = build_exact_index_from_dataframe(df)
    _write_json(index, target_path)
    logger.info("Built exact index: articles=%s output=%s", df.height, target_path)
    return index


def build_exact_index_from_dataframe(df: pl.DataFrame) -> dict[str, Any]:
    """Build exact index dict from canonical legal article rows."""

    _validate_columns(df)

    by_law_id: dict[str, list[str]] = defaultdict(list)
    by_article_no: dict[str, list[str]] = defaultdict(list)
    by_law_article: dict[str, list[str]] = defaultdict(list)
    accounting_accounts: dict[str, list[str]] = defaultdict(list)
    deadline_numbers: dict[str, list[str]] = defaultdict(list)
    sanction_terms: dict[str, list[str]] = defaultdict(list)
    article_payloads: dict[str, dict[str, Any]] = {}

    for row in df.iter_rows(named=True):
        article_id = _required_text(row.get("article_id"), "article_id")
        law_id = normalize_vietnamese_text(row.get("law_id"))
        article_no = normalize_article_no(row.get("article_no"))
        article_text = normalize_vietnamese_text(row.get("article_text"))

        if not law_id or not article_no or not article_text:
            logger.warning("Skipping exact index row with missing fields: article_id=%s", article_id)
            continue

        payload = _build_article_payload(row, article_no=article_no)
        article_payloads[article_id] = payload
        _append_unique(by_law_id[law_id], article_id)
        _append_unique(by_article_no[article_no], article_id)
        _append_unique(by_law_article[_law_article_key(law_id, article_no)], article_id)

        searchable_text = " ".join(
            [
                normalize_vietnamese_text(row.get("law_title")),
                normalize_vietnamese_text(row.get("article_title")),
                article_text,
            ]
        )
        for account in extract_accounting_accounts(searchable_text):
            _append_unique(accounting_accounts[account], article_id)
        for deadline in extract_deadline_numbers(searchable_text):
            _append_unique(deadline_numbers[deadline], article_id)
        for sanction_term in extract_sanction_terms(searchable_text):
            _append_unique(sanction_terms[sanction_term], article_id)

    return {
        "metadata": {
            "source": "legal_articles.parquet",
            "schema_version": 1,
            "article_count": len(article_payloads),
            "note": "Exact index is article-level canonical registry; it must not use chunk_id for citation.",
        },
        "articles": article_payloads,
        "by_law_id": _sort_index_values(by_law_id),
        "by_article_no": _sort_index_values(by_article_no),
        "by_law_article": _sort_index_values(by_law_article),
        "accounting_accounts": _sort_index_values(accounting_accounts),
        "deadline_numbers": _sort_index_values(deadline_numbers),
        "sanction_terms": _sort_index_values(sanction_terms),
    }


def load_exact_index(path: str | Path) -> dict[str, Any]:
    """Load exact index JSON from disk."""

    with Path(path).open("r", encoding="utf-8") as file:
        loaded = json.load(file)
    if not isinstance(loaded, dict):
        raise ValueError(f"Exact index must be a JSON object: {path}")
    return loaded


def extract_accounting_accounts(text: str) -> list[str]:
    """Extract accounting account numbers from legal text."""

    normalized = normalize_vietnamese_text(text)
    return sorted({match.group("account") for match in ACCOUNTING_ACCOUNT_PATTERN.finditer(normalized)})


def extract_deadline_numbers(text: str) -> list[str]:
    """Extract simple deadline number keys from legal text."""

    normalized = normalize_vietnamese_text(text)
    return sorted(
        {
            normalize_vietnamese_text(match.group(0)).casefold()
            for match in DEADLINE_NUMBER_PATTERN.finditer(normalized)
        }
    )


def extract_sanction_terms(text: str) -> list[str]:
    """Extract sanction-related terms and amount expressions."""

    normalized = normalize_vietnamese_text(text)
    lowered = normalized.casefold()
    terms = {keyword for keyword in SANCTION_KEYWORDS if keyword.casefold() in lowered}
    terms.update(
        normalize_vietnamese_text(match.group(0)).casefold()
        for match in SANCTION_AMOUNT_PATTERN.finditer(normalized)
    )
    return sorted(terms)


def _read_legal_articles(input_path: Path) -> pl.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Exact index source parquet not found: {input_path}")
    df = pl.read_parquet(input_path)
    _validate_columns(df)
    return df.select(REQUIRED_COLUMNS)


def _validate_columns(df: pl.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns for exact index: {missing_columns}")


def _build_article_payload(row: dict[str, Any], *, article_no: str) -> dict[str, Any]:
    return {
        "article_id": _required_text(row.get("article_id"), "article_id"),
        "law_id": normalize_vietnamese_text(row.get("law_id")),
        "law_title": normalize_vietnamese_text(row.get("law_title")),
        "article_no": article_no,
        "article_title": normalize_vietnamese_text(row.get("article_title")),
        "source_url": normalize_vietnamese_text(row.get("source_url")),
        "domain": normalize_vietnamese_text(row.get("domain")),
        "status": normalize_vietnamese_text(row.get("status")),
    }


def _write_json(index: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(index, file, ensure_ascii=False, indent=2)


def _required_text(value: Any, field_name: str) -> str:
    text = normalize_vietnamese_text(value)
    if not text:
        raise ValueError(f"Missing required exact index field: {field_name}")
    return text


def _law_article_key(law_id: str, article_no: str) -> str:
    return f"{law_id}|{article_no}"


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _sort_index_values(index: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in sorted(index.items())}
