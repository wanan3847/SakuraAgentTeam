"""LLM Provider module.

This module provides unified access to multiple LLM providers.

通过 litellm 一行支持 100+ 提供商（OpenAI / Anthropic / Google / Mistral /
DeepSeek / Qwen / Zhipu / Ollama / vLLM / Azure / Bedrock / Groq / Together /
OpenRouter …）。详见 app.foundation.llm.litellm_provider.COMMON_PROVIDERS。
"""

from app.foundation.llm.base import (
    LLMProvider,
    LLMProviderFactory,
    LLMResponse,
    Message,
    MessageRole,
)

__all__ = [
    "LLMProvider",
    "LLMProviderFactory",
    "LLMResponse",
    "Message",
    "MessageRole",
    "OpenAIProvider",
    "AnthropicProvider",
    "LiteLLMProvider",
    "COMMON_PROVIDERS",
    "list_common_providers",
    "normalize_model_name",
]

# Lazy registration
OpenAIProvider = None  # type: ignore
AnthropicProvider = None  # type: ignore
LiteLLMProvider = None  # type: ignore

try:
    from app.foundation.llm.openai import OpenAIProvider  # noqa: F401

    LLMProviderFactory.register("openai", OpenAIProvider)
except Exception:  # pragma: no cover
    pass

try:
    from app.foundation.llm.anthropic import AnthropicProvider  # noqa: F401

    LLMProviderFactory.register("anthropic", AnthropicProvider)
except Exception:  # pragma: no cover
    pass

try:
    from app.foundation.llm.litellm_provider import (  # noqa: F401
        COMMON_PROVIDERS,
        LiteLLMProvider,
        list_common_providers,
        normalize_model_name,
    )

    LLMProviderFactory.register("litellm", LiteLLMProvider)
except Exception:  # pragma: no cover
    pass
