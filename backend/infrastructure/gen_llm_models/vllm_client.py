"""Thin client for OpenAI-compatible vLLM generation servers.

The client is intentionally small: it owns endpoint configuration, request
serialization, timeout, and retry behavior. Prompt construction and answer
post-processing belong to the QA modules in later Phase 5 tasks.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VLLMClientConfig:
    """Configuration for a vLLM OpenAI-compatible endpoint."""

    base_url: str | None = None
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    endpoint: str = "/chat/completions"
    temperature: float = 0.0
    max_tokens: int = 700
    timeout_seconds: int = 120
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    api_key: str | None = None
    disable_thinking: bool = False

    @classmethod
    def from_env(cls) -> "VLLMClientConfig":
        """Build config from environment variables and project defaults."""

        settings = get_settings()
        return cls(
            base_url=os.getenv("VLLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or None,
            model=os.getenv("VLLM_MODEL") or settings.models.generator_model,
            endpoint=os.getenv("VLLM_ENDPOINT", "/chat/completions"),
            temperature=float(os.getenv("VLLM_TEMPERATURE", settings.models.generator_temperature)),
            max_tokens=int(os.getenv("VLLM_MAX_TOKENS", settings.models.generator_max_new_tokens)),
            timeout_seconds=int(os.getenv("VLLM_TIMEOUT_SECONDS", "120")),
            max_retries=int(os.getenv("VLLM_MAX_RETRIES", "2")),
            retry_backoff_seconds=float(os.getenv("VLLM_RETRY_BACKOFF_SECONDS", "1.0")),
            api_key=os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None,
            disable_thinking=disable_thinking_from_env(prefix="VLLM"),
        )


def _with_disabled_thinking(payload: dict[str, Any]) -> dict[str, Any]:
    chat_template_kwargs = payload.get("chat_template_kwargs")
    if chat_template_kwargs is None:
        merged_kwargs: dict[str, Any] = {}
    elif isinstance(chat_template_kwargs, dict):
        merged_kwargs = dict(chat_template_kwargs)
    else:
        raise ValueError("chat_template_kwargs must be a mapping when provided")

    merged_kwargs["enable_thinking"] = False
    return {**payload, "chat_template_kwargs": merged_kwargs}


def disable_thinking_from_env(prefix: str) -> bool:
    disable_value = os.getenv(f"{prefix}_DISABLE_THINKING")
    if disable_value is not None:
        return _env_flag_enabled(disable_value)

    enable_value = os.getenv(f"{prefix}_ENABLE_THINKING")
    if enable_value is not None:
        return not _env_flag_enabled(enable_value)

    return False


def _env_flag_enabled(value: str) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "on"}


class VLLMClient:
    """Lazy vLLM client with a simple text-generation interface."""

    def __init__(self, config: VLLMClientConfig | None = None) -> None:
        self.config = config or VLLMClientConfig.from_env()

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a response for a prompt.

        Network access happens only inside this method. Callers may override
        request fields with kwargs such as model, temperature, max_tokens, or
        messages.
        """

        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt must not be empty")

        payload = self._build_payload(prompt, **kwargs)
        response = self._post_json(payload)
        return self._extract_text(response)

    def _build_payload(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [{"role": "user", "content": prompt}]

        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self.config.model),
            "messages": messages,
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
        }
        payload.update(kwargs)
        if self.config.disable_thinking:
            payload = _with_disabled_thinking(payload)
        return payload

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._build_url()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        request = Request(url=url, data=body, headers=headers, method="POST")
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                with urlopen(request, timeout=self.config.timeout_seconds) as response:
                    response_body = response.read().decode("utf-8")
                loaded = json.loads(response_body)
                if not isinstance(loaded, dict):
                    raise RuntimeError("LLM response must be a JSON object")
                return loaded
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break

                # Retry ngắn để chịu được lỗi transient của server vLLM khi mới warm up.
                sleep_seconds = self.config.retry_backoff_seconds * (attempt + 1)
                logger.warning("vLLM request failed; retrying in %.2fs", sleep_seconds, exc_info=exc)
                time.sleep(sleep_seconds)

        raise RuntimeError("vLLM generation request failed") from last_error

    def _build_url(self) -> str:
        if not self.config.base_url:
            raise RuntimeError(
                "VLLM base_url is not configured. Pass VLLMClientConfig(base_url=...) "
                "or set VLLM_BASE_URL/OPENAI_BASE_URL."
            )

        base_url = self.config.base_url.rstrip("/") + "/"
        endpoint = self.config.endpoint.lstrip("/")
        return urljoin(base_url, endpoint)

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LLM response does not contain choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("LLM choice must be a JSON object")

        message = first_choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"].strip()

        text = first_choice.get("text")
        if isinstance(text, str):
            return text.strip()

        raise RuntimeError("LLM response does not contain generated text")
