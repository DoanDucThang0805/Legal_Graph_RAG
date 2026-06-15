"""Project settings loader.

This module only centralizes configuration. Business modules should receive
settings from here instead of hard-coding paths, model names, or retrieval
defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.config.path_config import PathConfig, get_default_path_config


CONFIG_DIR = Path(__file__).resolve().parent
RETRIEVAL_CONFIG_FILE = CONFIG_DIR / "retrieval_config.yaml"
MODEL_CONFIG_FILE = CONFIG_DIR / "model_config.yaml"


@dataclass(frozen=True)
class ModelSettings:
    """Model defaults for embedding, generation, and optional reranking."""

    embedding_model: str
    generator_model: str
    reranker_model: str | None
    embedding_dimension: int
    query_instruction_prefix: str
    generator_temperature: float
    generator_max_new_tokens: int


@dataclass(frozen=True)
class RetrievalSettings:
    """Retrieval defaults shared by Phase 1-5."""

    top_k: int
    rrf_k: int
    max_articles: int
    legal_bm25_top_k: int
    legal_dense_top_k: int
    phapdien_bm25_top_k: int
    phapdien_dense_top_k: int
    exact_top_k: int
    rerank_top_k: int
    multi_hop_max_articles: int


@dataclass(frozen=True)
class Settings:
    """Top-level immutable project settings."""

    paths: PathConfig
    models: ModelSettings
    retrieval: RetrievalSettings


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping from disk.

    Raises:
        ValueError: If the YAML root is not a mapping.
    """

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"YAML config must be a mapping: {config_path}")
    return loaded


def _build_model_settings(config: dict[str, Any]) -> ModelSettings:
    models = config.get("models", {})
    generation = config.get("generation", {})
    embedding = config.get("embedding", {})

    return ModelSettings(
        embedding_model=str(models.get("embedding_model", "darklethelong/vnlegal-lal")),
        generator_model=str(models.get("generator_model", "Qwen/Qwen2.5-7B-Instruct")),
        reranker_model=models.get("reranker_model"),
        embedding_dimension=int(embedding.get("dimension", 1024)),
        query_instruction_prefix=str(
            embedding.get(
                "query_instruction_prefix",
                "Instruct: Given a Vietnamese legal question, retrieve relevant legal passages that answer the question\nQuery: ",
            )
        ),
        generator_temperature=float(generation.get("temperature", 0.0)),
        generator_max_new_tokens=int(generation.get("max_new_tokens", 700)),
    )


def _build_retrieval_settings(config: dict[str, Any]) -> RetrievalSettings:
    retrieval = config.get("retrieval", {})
    top_k = retrieval.get("top_k", {})
    article_selection = retrieval.get("article_selection", {})

    return RetrievalSettings(
        top_k=int(top_k.get("default", 100)),
        rrf_k=int(retrieval.get("rrf_k", 60)),
        max_articles=int(article_selection.get("default_max_articles", 7)),
        legal_bm25_top_k=int(top_k.get("legal_bm25", 80)),
        legal_dense_top_k=int(top_k.get("legal_dense", 80)),
        phapdien_bm25_top_k=int(top_k.get("phapdien_bm25", 50)),
        phapdien_dense_top_k=int(top_k.get("phapdien_dense", 50)),
        exact_top_k=int(top_k.get("exact", 30)),
        rerank_top_k=int(top_k.get("rerank", 100)),
        multi_hop_max_articles=int(article_selection.get("multi_hop_max_articles", 12)),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache project settings."""

    model_config = load_yaml_config(MODEL_CONFIG_FILE)
    retrieval_config = load_yaml_config(RETRIEVAL_CONFIG_FILE)

    return Settings(
        paths=get_default_path_config(),
        models=_build_model_settings(model_config),
        retrieval=_build_retrieval_settings(retrieval_config),
    )
