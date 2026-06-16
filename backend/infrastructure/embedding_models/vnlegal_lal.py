"""Embedding wrapper for darklethelong/vnlegal-lal.

The model is loaded through Hugging Face AutoModel instead of
sentence-transformers. This avoids trainer/apex side effects in NVIDIA
containers and makes the pooling strategy explicit.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class VNLegalLALEmbedder:
    """Lazy embedder for Vietnamese legal dense retrieval."""

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
        max_length: int = 2048,
        model: Any | None = None,
        tokenizer: Any | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_length <= 0:
            raise ValueError("max_length must be positive")

        settings = get_settings()
        self.model_name = model_name or settings.models.embedding_model
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.query_instruction_prefix = (
            query_instruction_prefix or settings.models.query_instruction_prefix
        )
        self.expected_dimension = expected_dimension or settings.models.embedding_dimension
        self.trust_remote_code = trust_remote_code
        self.max_length = max_length

        self._model = model
        self._tokenizer = tokenizer

    @property
    def tokenizer(self) -> Any:
        """Load tokenizer lazily."""

        if self._tokenizer is None:
            logger.info("Loading tokenizer: %s", self.model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=self.trust_remote_code,
            )
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

        return self._tokenizer

    @property
    def model(self) -> Any:
        """Load transformer model lazily."""

        if self._model is None:
            logger.info("Loading embedding model: %s on %s", self.model_name, self.device)
            try:
                self._model = AutoModel.from_pretrained(
                    self.model_name,
                    trust_remote_code=self.trust_remote_code,
                )
            except ValueError as exc:
                if "model type `qwen3`" in str(exc) or "model type 'qwen3'" in str(exc):
                    raise RuntimeError(
                        "Cannot load darklethelong/vnlegal-lal because the installed "
                        "Transformers version does not support model_type='qwen3'. "
                        "Use a transformers version with Qwen3 support."
                    ) from exc
                raise

            self._model.to(self.device)
            self._model.eval()

        return self._model

    def encode_query(self, query: str) -> list[float]:
        """Encode one legal question with the required instruction prefix."""

        vector = self.encode_queries([query])[0]
        self._validate_dimension(vector)
        return vector

    def encode_queries(self, queries: Sequence[str]) -> list[list[float]]:
        """Encode legal questions with the required instruction prefix."""

        if not queries:
            return []
        prepared_queries = [self._prepare_query(query) for query in queries]
        return self._encode_texts(prepared_queries)

    def encode_documents(self, documents: Sequence[str]) -> list[list[float]]:
        """Encode legal passages without the query instruction prefix."""

        if not documents:
            return []
        prepared_documents = [self._normalize_input_text(text) for text in documents]
        return self._encode_texts(prepared_documents)

    def embed_documents(self, documents: Sequence[str]) -> list[list[float]]:
        """Alias for callers that use embed_* naming."""

        return self.encode_documents(documents)

    def embed_queries(self, queries: Sequence[str]) -> list[list[float]]:
        """Alias for callers that use embed_* naming."""

        return self.encode_queries(queries)

    def _prepare_query(self, query: str) -> str:
        normalized_query = self._normalize_input_text(query)
        prefix = self.query_instruction_prefix.strip()
        return f"{prefix}\n{normalized_query}"

    def _encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            vectors.extend(self._encode_batch(batch))

        if vectors:
            self._validate_dimension(vectors[0])
        return vectors

    @torch.inference_mode()
    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode one batch with last-token pooling.

        The last non-padding token is selected through attention_mask so this
        works for both left-padded and right-padded decoder-only models.
        """

        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        outputs = self.model(**encoded)
        hidden_states = outputs.last_hidden_state
        attention_mask = encoded["attention_mask"]

        seq_len = attention_mask.shape[1]
        positions = torch.arange(seq_len, device=self.device).unsqueeze(0)
        last_token_indices = (attention_mask * positions).max(dim=1).values.long()
        batch_indices = torch.arange(hidden_states.shape[0], device=self.device)
        embeddings = hidden_states[batch_indices, last_token_indices]

        if self.normalize_embeddings:
            embeddings = F.normalize(embeddings, p=2, dim=1)

        embeddings = embeddings.detach().cpu().float().numpy()
        return [vector.astype(float).tolist() for vector in embeddings]

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
