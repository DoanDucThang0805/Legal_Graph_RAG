"""Qwen generation client.

Qwen is served through the same OpenAI-compatible protocol as vLLM in this
project, so this wrapper only provides Qwen-specific environment names and a
clear import path for downstream QA code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from backend.config.settings import get_settings
from backend.infrastructure.gen_llm_models.vllm_client import VLLMClient, VLLMClientConfig


@dataclass(frozen=True)
class QwenClientConfig(VLLMClientConfig):
    """Configuration for Qwen models served by vLLM/OpenAI-compatible APIs."""

    @classmethod
    def from_env(cls) -> "QwenClientConfig":
        """Build Qwen config from env variables and project model defaults."""

        settings = get_settings()
        return cls(
            base_url=os.getenv("QWEN_BASE_URL")
            or os.getenv("VLLM_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or None,
            model=os.getenv("QWEN_MODEL") or os.getenv("VLLM_MODEL") or settings.models.generator_model,
            endpoint=os.getenv("QWEN_ENDPOINT", os.getenv("VLLM_ENDPOINT", "/chat/completions")),
            temperature=float(
                os.getenv("QWEN_TEMPERATURE", os.getenv("VLLM_TEMPERATURE", settings.models.generator_temperature))
            ),
            max_tokens=int(
                os.getenv("QWEN_MAX_TOKENS", os.getenv("VLLM_MAX_TOKENS", settings.models.generator_max_new_tokens))
            ),
            timeout_seconds=int(os.getenv("QWEN_TIMEOUT_SECONDS", os.getenv("VLLM_TIMEOUT_SECONDS", "120"))),
            max_retries=int(os.getenv("QWEN_MAX_RETRIES", os.getenv("VLLM_MAX_RETRIES", "2"))),
            retry_backoff_seconds=float(
                os.getenv("QWEN_RETRY_BACKOFF_SECONDS", os.getenv("VLLM_RETRY_BACKOFF_SECONDS", "1.0"))
            ),
            api_key=os.getenv("QWEN_API_KEY") or os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None,
        )


class QwenClient(VLLMClient):
    """Qwen-specialized alias over the vLLM OpenAI-compatible client."""

    def __init__(self, config: QwenClientConfig | None = None) -> None:
        super().__init__(config or QwenClientConfig.from_env())
