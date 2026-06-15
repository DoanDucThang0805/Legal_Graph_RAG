"""Embedding wrapper for darklethelong/vnlegal-lal."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class VNLegalLALEmbedder:
    """Lazy wrapper around the Vietnamese legal embedding model."""

    def __init__(
        self,
        model_name: str | None = None,
        *,
        batch_size: int = 32,
        normalize_embeddings: bool = True,
        device: str | None = None,
        query_instruction_prefix: str | None = None,
        expected_dimension: int | None = None,
        trust_remote_code: bool = True,
        model: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.models.embedding_model
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.device = device
        self.query_instruction_prefix = (
            query_instruction_prefix or settings.models.query_instruction_prefix
        )
        self.expected_dimension = expected_dimension or settings.models.embedding_dimension
        self.trust_remote_code = trust_remote_code
        self._model = model

    @property
    def model(self) -> Any:
        """Load the SentenceTransformer model on first use."""

        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError("Missing dependency: sentence-transformers") from exc

            logger.info("Loading embedding model: %s", self.model_name)
            kwargs: dict[str, Any] = {}
            if self.device:
                kwargs["device"] = self.device
            kwargs["trust_remote_code"] = self.trust_remote_code
            try:
                self._model = SentenceTransformer(self.model_name, **kwargs)
            except ValueError as exc:
                if "model type `qwen3`" in str(exc) or "model type 'qwen3'" in str(exc):
                    raise RuntimeError(
                        "Cannot load darklethelong/vnlegal-lal because the installed "
                        "Transformers version does not support model_type='qwen3'. "
                        "Run: pip install -r backend/requirements.txt"
                    ) from exc
                raise

        return self._model

    def encode_query(self, query: str) -> list[float]:
        """Encode one legal question with the required instruction prefix."""

        prepared_query = self._prepare_query(query)
        vector = self._encode_batch([prepared_query])[0]
        self._validate_dimension(vector)
        return vector

    def encode_documents(self, documents: Sequence[str]) -> list[list[float]]:
        """Encode legal passages without the query instruction prefix."""

        if not documents:
            return []

        prepared_documents = [self._normalize_input_text(text) for text in documents]
        vectors: list[list[float]] = []
        for start in range(0, len(prepared_documents), self.batch_size):
            batch = prepared_documents[start : start + self.batch_size]
            vectors.extend(self._encode_batch(batch))

        if vectors:
            self._validate_dimension(vectors[0])
        return vectors

    def _prepare_query(self, query: str) -> str:
        normalized_query = self._normalize_input_text(query)
        prefix = self.query_instruction_prefix
        if not prefix.endswith((" ", "\n")):
            prefix = f"{prefix}\n"
        return f"{prefix}{normalized_query}"

    def _encode_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode one batch and return plain Python float lists."""

        encoded = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vector.astype(float).tolist() for vector in encoded]

    @staticmethod
    def _normalize_input_text(text: str) -> str:
        if text is None:
            raise ValueError("Text to embed must not be None")
        normalized = str(text).strip()
        if not normalized:
            raise ValueError("Text to embed must not be empty")
        return normalized

    def _validate_dimension(self, vector: Sequence[float]) -> None:
        """Validate embedding dimension to avoid mixing incompatible indexes."""

        dimension = len(vector)
        if dimension != self.expected_dimension:
            raise ValueError(
                f"Unexpected embedding dimension: expected {self.expected_dimension}, got {dimension}"
            )
