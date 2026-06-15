"""Thin OpenSearch client wrapper.

This module only owns connection setup and health checks. Index creation and
search logic belong to indexing/retrieval modules.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenSearchClientConfig:
    """Connection settings for a local or remote OpenSearch service."""

    host: str = "localhost"
    port: int = 9200
    scheme: str = "http"
    username: str | None = None
    password: str | None = None
    verify_certs: bool = False
    timeout_seconds: int = 10

    @classmethod
    def from_env(cls) -> "OpenSearchClientConfig":
        """Build config from environment variables with local defaults."""

        return cls(
            host=os.getenv("OPENSEARCH_HOST", "localhost"),
            port=int(os.getenv("OPENSEARCH_PORT", "9200")),
            scheme=os.getenv("OPENSEARCH_SCHEME", "http"),
            username=os.getenv("OPENSEARCH_USERNAME") or None,
            password=os.getenv("OPENSEARCH_PASSWORD") or None,
            verify_certs=os.getenv("OPENSEARCH_VERIFY_CERTS", "false").lower() == "true",
            timeout_seconds=int(os.getenv("OPENSEARCH_TIMEOUT_SECONDS", "10")),
        )


class OpenSearchClient:
    """Lazy OpenSearch client used by indexing and retrieval code."""

    def __init__(
        self,
        config: OpenSearchClientConfig | None = None,
        client: Any | None = None,
    ) -> None:
        self.config = config or OpenSearchClientConfig.from_env()
        self._client = client

    @property
    def client(self) -> Any:
        """Return a lazily constructed OpenSearch SDK client."""

        if self._client is None:
            try:
                from opensearchpy import OpenSearch
            except ImportError as exc:
                raise RuntimeError("Missing dependency: opensearch-py") from exc

            auth = None
            if self.config.username and self.config.password:
                auth = (self.config.username, self.config.password)

            self._client = OpenSearch(
                hosts=[
                    {
                        "host": self.config.host,
                        "port": self.config.port,
                        "scheme": self.config.scheme,
                    }
                ],
                http_auth=auth,
                verify_certs=self.config.verify_certs,
                timeout=self.config.timeout_seconds,
            )

        return self._client

    def health_check(self) -> bool:
        """Return True when OpenSearch responds to ping."""

        try:
            return bool(self.client.ping())
        except Exception:
            logger.exception("OpenSearch health check failed")
            return False
