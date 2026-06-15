"""Phase 1 corpus build orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.config.settings import get_settings
from backend.knowledge_processing.extract_articles import extract_articles_from_vbpl
from backend.knowledge_processing.load_anle import load_anle_sentences
from backend.knowledge_processing.load_phapdien import load_phapdien_articles
from backend.knowledge_processing.load_testset import load_test_questions
from backend.knowledge_processing.load_vbpl import load_vbpl_documents
from backend.knowledge_processing.map_phapdien_to_vbpl import build_phapdien_to_vbpl_map

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorpusBuildStep:
    name: str
    output_path: Path
    run: Callable[[], object]


def build_phase1_corpus(skip_existing: bool = False) -> None:
    """Run all Phase 1 data-loading and canonical corpus steps in order."""

    settings = get_settings()
    paths = settings.paths
    _validate_required_inputs(paths.raw_dir / "R2AIStage1DATA.json")

    steps = [
        CorpusBuildStep(
            name="load_testset",
            output_path=paths.processed_dir / "test_questions.parquet",
            run=lambda: load_test_questions(
                paths.raw_dir / "R2AIStage1DATA.json",
                paths.processed_dir / "test_questions.parquet",
            ),
        ),
        CorpusBuildStep(
            name="load_phapdien",
            output_path=paths.processed_dir / "phapdien_articles.parquet",
            run=lambda: load_phapdien_articles(paths.processed_dir / "phapdien_articles.parquet"),
        ),
        CorpusBuildStep(
            name="load_anle",
            output_path=paths.processed_dir / "anle_units.parquet",
            run=lambda: load_anle_sentences(paths.processed_dir / "anle_units.parquet"),
        ),
        CorpusBuildStep(
            name="load_vbpl",
            output_path=paths.processed_dir / "legal_documents.parquet",
            run=lambda: load_vbpl_documents(paths.processed_dir / "legal_documents.parquet"),
        ),
        CorpusBuildStep(
            name="extract_legal_articles",
            output_path=paths.processed_dir / "legal_articles.parquet",
            run=lambda: extract_articles_from_vbpl(
                paths.processed_dir / "legal_documents.parquet",
                paths.processed_dir / "legal_articles.parquet",
            ),
        ),
        CorpusBuildStep(
            name="map_phapdien_to_vbpl",
            output_path=paths.processed_dir / "phapdien_to_vbpl_map.parquet",
            run=lambda: build_phapdien_to_vbpl_map(
                paths.processed_dir / "phapdien_articles.parquet",
                paths.processed_dir / "legal_articles.parquet",
                paths.processed_dir / "phapdien_to_vbpl_map.parquet",
            ),
        ),
    ]

    for step in steps:
        _run_step(step, skip_existing=skip_existing)

    logger.info("Phase 1 corpus build completed")


def _validate_required_inputs(testset_path: Path) -> None:
    if not testset_path.exists():
        raise FileNotFoundError(f"Missing required testset input: {testset_path}")


def _run_step(step: CorpusBuildStep, skip_existing: bool) -> None:
    if skip_existing and step.output_path.exists():
        logger.info("Skipping existing step=%s output=%s", step.name, step.output_path)
        return

    logger.info("Starting step=%s output=%s", step.name, step.output_path)
    try:
        step.run()
    except Exception:
        logger.exception("Failed step=%s", step.name)
        raise
    logger.info("Finished step=%s output=%s", step.name, step.output_path)
