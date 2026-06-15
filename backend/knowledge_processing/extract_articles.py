"""Extract canonical legal articles from normalized VBPL documents."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import ValidationError

from backend.config.settings import get_settings
from backend.knowledge_processing.hf_loader import save_parquet
from backend.knowledge_processing.normalize_text import (
    normalize_article_no,
    normalize_vietnamese_text,
)
from backend.schema.legal_article import LegalArticle

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
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

ARTICLE_HEADING_PATTERN = re.compile(
    r"(?:^|\s|#{1,6}\s*)"
    r"(?P<label>Điều|điều|DIEU|Dieu|dieu)\s+0*(?P<number>\d+[a-zA-Z]?)"
    r"\s*[\.:]?",
    re.IGNORECASE,
)


def extract_articles_from_vbpl(
    input_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> pl.DataFrame:
    """Extract article-level canonical rows from legal_documents.parquet."""

    settings = get_settings()
    source_path = (
        Path(input_path)
        if input_path is not None
        else settings.paths.processed_dir / "legal_documents.parquet"
    )
    target_path = (
        Path(output_path)
        if output_path is not None
        else settings.paths.processed_dir / "legal_articles.parquet"
    )

    documents_df = pl.read_parquet(source_path)
    articles = extract_articles_from_documents(documents_df)
    output_df = _articles_to_dataframe(articles)
    save_parquet(output_df, target_path)
    logger.info("Extracted legal articles: rows=%s output=%s", output_df.height, target_path)
    return output_df


def extract_articles_from_documents(documents_df: pl.DataFrame) -> list[LegalArticle]:
    """Extract and validate article rows from a document DataFrame."""

    articles: list[LegalArticle] = []
    seen_article_ids: set[str] = set()
    documents_without_articles = 0
    invalid_articles = 0

    for document in documents_df.iter_rows(named=True):
        document_articles = _extract_articles_from_document(document)
        if not document_articles:
            documents_without_articles += 1
            logger.warning("No articles extracted from document: doc_id=%s", document.get("doc_id"))
            continue

        for article_data in document_articles:
            try:
                article = LegalArticle(**article_data)
            except ValidationError as exc:
                invalid_articles += 1
                logger.warning("Invalid extracted article skipped: error=%s data=%s", exc, article_data)
                continue

            if article.article_id in seen_article_ids:
                logger.warning("Duplicate article_id skipped: article_id=%s", article.article_id)
                continue

            seen_article_ids.add(article.article_id)
            articles.append(article)

    if documents_without_articles:
        logger.warning("Documents without extracted articles: count=%s", documents_without_articles)
    if invalid_articles:
        logger.warning("Invalid extracted articles skipped: count=%s", invalid_articles)
    if not articles:
        raise ValueError("No legal articles extracted from VBPL documents")

    return articles


def _extract_articles_from_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    law_id = normalize_vietnamese_text(document.get("law_id"))
    law_title = normalize_vietnamese_text(document.get("law_title"))
    markdown = normalize_vietnamese_text(document.get("markdown"))
    source_url = normalize_vietnamese_text(document.get("source_url"))
    domain = normalize_vietnamese_text(document.get("legal_area"))
    status = normalize_vietnamese_text(document.get("status"))

    if not law_id or not law_title or not markdown:
        logger.warning(
            "Document missing required extraction fields: doc_id=%s law_id=%s",
            document.get("doc_id"),
            law_id,
        )
        return []

    matches = list(ARTICLE_HEADING_PATTERN.finditer(markdown))
    if not matches:
        return []

    articles: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        article_no = normalize_article_no(f"Điều {match.group('number')}")
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        article_text = normalize_vietnamese_text(markdown[start:end])
        article_text = _strip_markdown_heading_prefix(article_text)

        if not article_no or len(article_text) < 20:
            continue

        article_title = _extract_article_title(article_no, article_text)
        article_id = build_article_id(law_id, law_title, article_no)
        articles.append(
            {
                "article_id": article_id,
                "law_id": law_id,
                "law_title": law_title,
                "article_no": article_no,
                "article_title": article_title,
                "article_text": article_text,
                "source_url": source_url,
                "domain": domain,
                "status": status,
            }
        )

    return articles


def build_article_id(law_id: str, law_title: str, article_no: str) -> str:
    """Build canonical article_id used by retrieval and submission layers."""

    return f"{law_id}|{law_title}|{article_no}"


def _strip_markdown_heading_prefix(text: str) -> str:
    return normalize_vietnamese_text(re.sub(r"^#{1,6}\s*", "", text))


def _extract_article_title(article_no: str, article_text: str) -> str | None:
    body = article_text
    if body.casefold().startswith(article_no.casefold()):
        body = body[len(article_no) :].lstrip(" .:-")

    if not body:
        return None

    first_sentence = re.split(r"(?<=[\.!?])\s+", body, maxsplit=1)[0]
    title = normalize_vietnamese_text(first_sentence)
    if 0 < len(title) <= 180:
        return title
    return None


def _articles_to_dataframe(articles: list[LegalArticle]) -> pl.DataFrame:
    rows = [article.model_dump() for article in articles]
    if not rows:
        return pl.DataFrame(schema={column: pl.Utf8 for column in OUTPUT_COLUMNS})
    return pl.DataFrame(rows).select(OUTPUT_COLUMNS)
