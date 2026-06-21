"""Regenerate answers only for IDs from unsupported citation report."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.settings import get_settings
from backend.evaluation.subset_answer_regeneration import generate_unsupported_citation_subset
from backend.infrastructure.gen_llm_models.qwen_client import QwenClient
from backend.infrastructure.gen_llm_models.vllm_client import VLLMClient
from backend.qa.answer_generator import AnswerGenerator

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    generator = AnswerGenerator(llm_client=_build_llm_client(args.client))
    summary = generate_unsupported_citation_subset(
        unsupported_report_path=args.unsupported_report,
        retrieval_results_path=args.retrieval_results,
        output_path=args.output,
        legal_articles_path=args.legal_articles_path,
        generator=generator,
        max_tokens=args.max_tokens,
        max_article_chars=args.max_article_chars,
        max_total_context_chars=args.max_total_context_chars,
    )
    logger.info("Summary: %s", summary)
    print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    output_dir = settings.paths.output_dir
    parser = argparse.ArgumentParser(description="Regenerate QA answers for unsupported citation subset only.")
    parser.add_argument(
        "--unsupported-report",
        default=str(output_dir / "error_analysis_v2" / "unsupported_citations_report.csv"),
    )
    parser.add_argument("--retrieval-results", default=str(output_dir / "retrieval_results.jsonl"))
    parser.add_argument("--output", default=str(output_dir / "generated_answers_v2_p6r4_subset_unsupported.jsonl"))
    parser.add_argument("--legal-articles-path", default=str(settings.paths.processed_dir / "legal_articles.parquet"))
    parser.add_argument("--client", choices=["qwen", "vllm"], default="qwen")
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--max-article-chars", type=int, default=700)
    parser.add_argument("--max-total-context-chars", type=int, default=2500)
    parser.add_argument("--log-level", default="INFO")
    return parser


def _build_llm_client(client_name: str) -> QwenClient | VLLMClient:
    if client_name == "vllm":
        return VLLMClient()
    return QwenClient()


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
