"""LLM Provider module.

This module provides unified access to multiple LLM providers.
"""

from app.foundation.llm.base import (
    LLMProvider,
    LLMProviderFactory,
    LLMResponse,
    Message,
    MessageRole,
)

# Providers are optional - only register if the package is installed.
# This avoids hard dependencies on users who don't need a specific provider.
__all__ = [
    "LLMProvider",
    "LLMProviderFactory",
    "LLMResponse",
    "Message",
    "MessageRole",
    "OpenAIProvider",
    "AnthropicProvider",
]

# Lazy registration: define placeholders for providers
# Import modules inside a try/except to avoid requiring every package installed
OpenAIProvider = None  # type: ignore
AnthropicProvider = None  # type: ignore

try:
    from app.foundation.llm.openai import OpenAIProvider  # noqa: F401

    LLMProviderFactory.register("openai", OpenAIProvider)
except Exception:  # pragma: no cover - missing dependency
    pass

try:
    from app.foundation.llm.anthropic import AnthropicProvider  # noqa: F401

    LLMProviderFactory.register("anthropic", AnthropicProvider)
except Exception:  # pragma: no cover - missing dependency
    pass
