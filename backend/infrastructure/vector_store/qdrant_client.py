"""Thin Qdrant client wrapper.

This module avoids creating collections at import or construction time. Index
builders are responsible for collection schemas and payload design.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QdrantClientConfig:
    """Connection settings for Qdrant."""

    host: str = "localhost"
    port: int = 6333
    https: bool = False
    api_key: str | None = None
    timeout_seconds: int = 10

    @classmethod
    def from_env(cls) -> "QdrantClientConfig":
        """Build config from environment variables with local defaults."""

        return cls(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            https=os.getenv("QDRANT_HTTPS", "false").lower() == "true",
            api_key=os.getenv("QDRANT_API_KEY") or None,
            timeout_seconds=int(os.getenv("QDRANT_TIMEOUT_SECONDS", "10")),
        )


class QdrantClient:
    """Lazy Qdrant SDK wrapper used by indexing and dense retrieval."""

    def __init__(
        self,
        config: QdrantClientConfig | None = None,
        client: Any | None = None,
    ) -> None:
        self.config = config or QdrantClientConfig.from_env()
        self._client = client

    @property
    def client(self) -> Any:
        """Return a lazily constructed Qdrant SDK client."""

        if self._client is None:
            try:
                from qdrant_client import QdrantClient as SDKQdrantClient
            except ImportError as exc:
                raise RuntimeError("Missing dependency: qdrant-client") from exc

            self._client = SDKQdrantClient(
                host=self.config.host,
                port=self.config.port,
                https=self.config.https,
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds,
            )

        return self._client

    def health_check(self) -> bool:
        """Return True when Qdrant responds to a lightweight API call."""

        try:
            self.client.get_collections()
            return True
        except Exception:
            logger.exception("Qdrant health check failed")
            return False
