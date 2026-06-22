from backend.infrastructure.gen_llm_models.vllm_client import VLLMClient, VLLMClientConfig


def test_default_payload_omits_chat_template_kwargs() -> None:
    client = VLLMClient(config=VLLMClientConfig(base_url="http://localhost:8000/v1"))

    payload = client._build_payload("short prompt")

    assert "chat_template_kwargs" not in payload


def test_disable_thinking_config_adds_chat_template_kwargs() -> None:
    client = VLLMClient(
        config=VLLMClientConfig(
            base_url="http://localhost:8000/v1",
            disable_thinking=True,
        )
    )

    payload = client._build_payload("short prompt")

    assert payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_disable_thinking_merges_existing_chat_template_kwargs() -> None:
    client = VLLMClient(
        config=VLLMClientConfig(
            base_url="http://localhost:8000/v1",
            disable_thinking=True,
        )
    )

    payload = client._build_payload(
        "short prompt",
        chat_template_kwargs={"tokenize": False, "enable_thinking": True},
    )

    assert payload["chat_template_kwargs"] == {
        "tokenize": False,
        "enable_thinking": False,
    }


def test_disable_thinking_from_env(monkeypatch) -> None:
    monkeypatch.setenv("VLLM_DISABLE_THINKING", "1")

    config = VLLMClientConfig.from_env()

    assert config.disable_thinking is True


def test_enable_thinking_false_from_env_disables_thinking(monkeypatch) -> None:
    monkeypatch.delenv("VLLM_DISABLE_THINKING", raising=False)
    monkeypatch.setenv("VLLM_ENABLE_THINKING", "false")

    config = VLLMClientConfig.from_env()

    assert config.disable_thinking is True
