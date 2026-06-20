"""Tests for LLM providers."""

import pytest

from app.foundation.llm import (
    LLMProviderFactory,
    Message,
    MessageRole,
)


def test_message_to_dict():
    """Test Message serialization."""
    msg = Message(role=MessageRole.USER, content="Hello")
    result = msg.to_dict()

    assert result["role"] == "user"
    assert result["content"] == "Hello"


def test_llm_provider_factory_list():
    """Test listing available providers."""
    providers = LLMProviderFactory.list_providers()

    assert "openai" in providers
    assert "anthropic" in providers


def test_llm_provider_factory_create_openai():
    """Test creating OpenAI provider."""
    provider = LLMProviderFactory.create(
        provider="openai",
        model="gpt-4o",
        api_key="test-key",
    )

    assert provider.model == "gpt-4o"
    assert provider.api_key == "test-key"


def test_llm_provider_factory_create_anthropic():
    """Test creating Anthropic provider."""
    provider = LLMProviderFactory.create(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        api_key="test-key",
    )

    assert provider.model == "claude-sonnet-4-20250514"
    assert provider.api_key == "test-key"


def test_llm_provider_factory_invalid():
    """Test creating invalid provider."""
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMProviderFactory.create(
            provider="invalid",
            model="test",
        )
