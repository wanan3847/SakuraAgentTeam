"""LiteLLM Provider 测试 — 不打真实 API，只验证接口与注册。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.foundation.llm import (
    COMMON_PROVIDERS,
    LLMProviderFactory,
    Message,
    MessageRole,
    list_common_providers,
    normalize_model_name,
)


def test_factory_has_litellm():
    """litellm 已注册到 factory。"""
    providers = LLMProviderFactory.list_providers()
    assert "litellm" in providers
    assert "openai" in providers
    assert "anthropic" in providers


def test_factory_create_litellm():
    """通过 factory 创建 litellm provider。"""
    p = LLMProviderFactory.create("litellm", model="openai/gpt-4o", api_key="sk-test")
    assert p.model == "openai/gpt-4o"
    assert p.api_key == "sk-test"


def test_factory_create_with_base_url():
    """Ollama / vLLM 自定义 base_url。"""
    p = LLMProviderFactory.create(
        "litellm",
        model="ollama/llama3",
        api_key="ollama",
        base_url="http://localhost:11434",
    )
    assert p.base_url == "http://localhost:11434"


def test_factory_create_unknown_raises():
    """未知 provider 抛 ValueError。"""
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMProviderFactory.create("nope", model="x")


def test_common_providers_count():
    """至少 20 个常用 provider 文档。"""
    assert len(COMMON_PROVIDERS) >= 20
    prefixes = [p[0] for p in COMMON_PROVIDERS]
    # 关键 provider 都列了
    for required in ("openai", "anthropic", "ollama", "deepseek", "gemini", "bedrock"):
        assert required in prefixes, f"缺少 {required}"


def test_list_common_providers_returns_dicts():
    items = list_common_providers()
    assert isinstance(items, list)
    assert all("prefix" in it and "description" in it for it in items)


def test_normalize_short_model():
    assert normalize_model_name("gpt-4o") == "openai/gpt-4o"
    assert normalize_model_name("claude-3-5-sonnet-20241022") == "openai/claude-3-5-sonnet-20241022"


def test_normalize_already_prefixed():
    """已含 / 的模型名原样返回。"""
    assert normalize_model_name("ollama/llama3") == "ollama/llama3"
    assert normalize_model_name("anthropic/claude-3") == "anthropic/claude-3"
    assert normalize_model_name("bedrock/anthropic.claude-3") == "bedrock/anthropic.claude-3"


def test_normalize_default_provider():
    """短名 + 自定义默认 provider。"""
    assert normalize_model_name("llama3", default_provider="ollama") == "ollama/llama3"
    assert normalize_model_name("deepseek-chat", default_provider="deepseek") == "deepseek/deepseek-chat"


def test_chat_passes_correct_params():
    """chat() 正确构造 litellm.completion 参数。"""
    from app.foundation.llm.litellm_provider import LiteLLMProvider

    p = LiteLLMProvider(
        model="anthropic/claude-3-5-sonnet-20241022",
        api_key="sk-ant-test",
        temperature=0.7,
        max_tokens=2048,
    )
    msgs = [Message(role=MessageRole.USER, content="hi")]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "hello"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.model = "claude-3-5-sonnet-20241022"
    mock_response.usage.prompt_tokens = 5
    mock_response.usage.completion_tokens = 3
    mock_response.usage.total_tokens = 8

    with patch("litellm.completion", return_value=mock_response) as mock_call:
        result = p.chat(msgs)
        assert result.content == "hello"
        assert result.finish_reason == "stop"
        assert result.usage["total_tokens"] == 8

        # 验证传给 litellm.completion 的参数
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs["model"] == "anthropic/claude-3-5-sonnet-20241022"
        assert call_kwargs["api_key"] == "sk-ant-test"
        assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]
        # 透传 config
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 2048


def test_achat_passes_correct_params():
    """achat() 用 litellm.acompletion。"""
    from app.foundation.llm.litellm_provider import LiteLLMProvider

    p = LiteLLMProvider(model="gpt-4o", api_key="sk-test")
    msgs = [Message(role=MessageRole.USER, content="x")]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "ok"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.model = "gpt-4o"
    mock_response.usage = None

    async def fake_acompletion(**_):
        return mock_response

    with patch("litellm.acompletion", side_effect=fake_acompletion) as mock_call:
        import asyncio

        result = asyncio.run(p.achat(msgs))
        assert result.content == "ok"
        # api_key 也得传
        assert mock_call.call_args.kwargs["api_key"] == "sk-test"


def test_stream_yields_chunks():
    """stream() 逐 chunk yield delta.content。"""
    from app.foundation.llm.litellm_provider import LiteLLMProvider

    p = LiteLLMProvider(model="gpt-4o", api_key="sk-test")
    msgs = [Message(role=MessageRole.USER, content="hi")]

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta.content = "你"
    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta.content = "好"
    chunk3 = MagicMock()
    chunk3.choices = [MagicMock()]
    chunk3.choices[0].delta.content = None  # 末尾空 chunk

    with patch("litellm.completion", return_value=[chunk1, chunk2, chunk3]):
        chunks = list(p.stream(msgs))
    assert chunks == ["你", "好"]


def test_base_url_passed_as_api_base():
    """base_url 转 litellm 的 api_base 参数。"""
    from app.foundation.llm.litellm_provider import LiteLLMProvider

    p = LiteLLMProvider(
        model="custom-model",
        api_key="any",
        base_url="http://localhost:8000/v1",
    )
    msgs = [Message(role=MessageRole.USER, content="x")]

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "ok"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.model = "custom"
    mock_response.usage = None

    with patch("litellm.completion", return_value=mock_response) as mock_call:
        p.chat(msgs)
        assert mock_call.call_args.kwargs["api_base"] == "http://localhost:8000/v1"
