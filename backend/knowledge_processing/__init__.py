"""Knowledge processing helpers for Legal Graph RAG."""

from backend.knowledge_processing.build_corpus import build_phase1_corpus
from backend.knowledge_processing.extract_articles import extract_articles_from_vbpl
from backend.knowledge_processing.hf_loader import load_hf_dataset_to_polars, save_parquet
from backend.knowledge_processing.load_anle import load_anle_sentences
from backend.knowledge_processing.load_phapdien import load_phapdien_articles
from backend.knowledge_processing.load_testset import load_test_questions
from backend.knowledge_processing.load_vbpl import load_vbpl_documents
from backend.knowledge_processing.map_phapdien_to_vbpl import build_phapdien_to_vbpl_map
from backend.knowledge_processing.prepare_index_corpus import prepare_index_corpus
from backend.knowledge_processing.normalize_text import (
    normalize_article_no,
    normalize_law_id,
    normalize_law_title,
    normalize_law_type,
    normalize_vietnamese_text,
)

__all__ = [
    "build_phase1_corpus",
    "extract_articles_from_vbpl",
    "build_phapdien_to_vbpl_map",
    "load_anle_sentences",
    "load_phapdien_articles",
    "load_test_questions",
    "load_vbpl_documents",
    "load_hf_dataset_to_polars",
    "prepare_index_corpus",
    "normalize_article_no",
    "normalize_law_id",
    "normalize_law_title",
    "normalize_law_type",
    "normalize_vietnamese_text",
    "save_parquet",
]
