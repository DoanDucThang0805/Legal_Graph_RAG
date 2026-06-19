"""Thin entrypoint for Phase 5 answer generation."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.settings import get_settings
from backend.infrastructure.gen_llm_models.qwen_client import QwenClient
from backend.infrastructure.gen_llm_models.vllm_client import VLLMClient
from backend.qa.answer_generator import AnswerGenerator
from backend.qa.article_context_loader import load_selected_article_contexts
from backend.qa.citation_postprocess import postprocess_citations

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    llm_client = _build_llm_client(args.client)
    generator = AnswerGenerator(llm_client=llm_client)
    summary = generate_answers_batch(
        input_path=args.input,
        output_path=args.output,
        legal_articles_path=args.legal_articles_path,
        generator=generator,
        limit=args.limit,
        max_tokens=args.max_tokens,
        max_article_chars=args.max_article_chars,
        max_total_context_chars=args.max_total_context_chars,
    )
    logger.info("Summary: %s", summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Generate grounded legal answers from retrieval results.")
    parser.add_argument("--input", default=str(settings.paths.output_dir / "retrieval_results.jsonl"))
    parser.add_argument("--output", default=str(settings.paths.output_dir / "generated_answers.jsonl"))
    parser.add_argument("--legal-articles-path", default=str(settings.paths.processed_dir / "legal_articles.parquet"))
    parser.add_argument("--client", choices=["qwen", "vllm"], default="qwen")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--max-article-chars", type=int, default=700)
    parser.add_argument("--max-total-context-chars", type=int, default=2500)
    parser.add_argument("--log-level", default="INFO")
    return parser


def generate_answers_batch(
    input_path: str | Path,
    output_path: str | Path,
    legal_articles_path: str | Path,
    generator: AnswerGenerator,
    limit: int | None = None,
    max_tokens: int = 128,
    max_article_chars: int = 700,
    max_total_context_chars: int = 2500,
) -> dict[str, int]:
    source_path = Path(input_path)
    target_path = Path(output_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"retrieval results file does not exist: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    processed_count = 0

    with source_path.open("r", encoding="utf-8") as source, target_path.open("w", encoding="utf-8") as target:
        for line_number, line in enumerate(source, start=1):
            if limit is not None and processed_count >= limit:
                break

            record = _load_jsonl_record(line, line_number)
            selected_article_ids = _extract_selected_article_ids(record)
            selected_articles = load_selected_article_contexts(
                selected_article_ids,
                legal_articles_path=legal_articles_path,
                max_article_chars=max_article_chars,
                max_total_context_chars=max_total_context_chars,
            )
            total_context_chars = _count_article_text_chars(selected_articles)
            logger.info(
                "Generating answer id=%s selected_articles=%d hydrated_articles=%d total_context_chars=%d max_tokens=%d",
                record.get("id"),
                len(selected_article_ids),
                len(selected_articles),
                total_context_chars,
                max_tokens,
            )

            answer = generator.generate_answer(
                question=str(record.get("question", "")),
                selected_articles=selected_articles,
                answer_type=str(record.get("answer_type", "general") or "general"),
                max_tokens=max_tokens,
            )
            answer = postprocess_citations(answer, selected_articles)

            output_record = {
                "id": record.get("id"),
                "question": record.get("question"),
                "answer": answer,
                "selected_articles": selected_articles,
            }
            target.write(json.dumps(output_record, ensure_ascii=False) + "\n")
            processed_count += 1

    return {"processed": processed_count}


def _build_llm_client(client_name: str) -> QwenClient | VLLMClient:
    if client_name == "vllm":
        return VLLMClient()
    return QwenClient()


def _load_jsonl_record(line: str, line_number: int) -> dict[str, Any]:
    try:
        loaded = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError(f"JSONL line {line_number} must be an object")
    return loaded


def _extract_selected_article_ids(record: dict[str, Any]) -> list[str]:
    selected_articles = record.get("selected_articles")
    if selected_articles is None:
        selected_articles = record.get("selected_article_ids", [])

    if not isinstance(selected_articles, list):
        raise ValueError("selected_articles must be a list")

    article_ids: list[str] = []
    for article in selected_articles:
        if isinstance(article, str):
            article_ids.append(article)
        elif isinstance(article, dict) and article.get("article_id"):
            article_ids.append(str(article["article_id"]))
    return article_ids


def _count_article_text_chars(selected_articles: list[dict[str, Any]]) -> int:
    return sum(len(str(article.get("article_text") or "")) for article in selected_articles)


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
