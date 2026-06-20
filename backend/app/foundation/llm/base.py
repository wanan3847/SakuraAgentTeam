"""LLM Provider abstraction layer.

This module provides a unified interface for different LLM providers,
supporting OpenAI, Anthropic, and local models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Iterator, List, Optional


class MessageRole(str, Enum):
    """Message role in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """A single message in the conversation."""

    role: MessageRole
    content: str

    def to_dict(self) -> dict:
        """Convert to dictionary format for API calls."""
        return {"role": self.role.value, "content": self.content}


@dataclass
class LLMResponse:
    """Response from LLM provider."""

    content: str
    model: str
    usage: Optional[dict] = None
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    This class defines the unified interface that all LLM providers must implement.
    Inspired by OpenHands SDK and Claude Code Tool abstraction.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize the LLM provider.

        Args:
            model: Model identifier (e.g., "gpt-4o", "claude-4-opus")
            api_key: API key for the provider
            base_url: Base URL for the API (for local models or proxies)
            **kwargs: Additional provider-specific configuration
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.config = kwargs

    @abstractmethod
    def chat(self, messages: List[Message], **kwargs: Any) -> LLMResponse:
        """Synchronous chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLM response
        """
        ...

    @abstractmethod
    async def achat(self, messages: List[Message], **kwargs: Any) -> LLMResponse:
        """Asynchronous chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters

        Returns:
            LLM response
        """
        ...

    @abstractmethod
    def stream(self, messages: List[Message], **kwargs: Any) -> Iterator[str]:
        """Streaming chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of the response text
        """
        ...

    @abstractmethod
    async def astream(self, messages: List[Message], **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronous streaming chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of the response text
        """
        ...

    def _prepare_messages(self, messages: List[Message]) -> List[dict]:
        """Prepare messages for API call.

        Args:
            messages: List of Message objects

        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in messages]


class LLMProviderFactory:
    """Factory for creating LLM provider instances.

    Supports multiple providers with unified configuration.
    Inspired by OpenHands support for 100+ models.
    """

    _providers: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None:
        """Register a new provider class.

        Args:
            name: Provider name (e.g., "openai", "anthropic")
            provider_class: Provider class to register
        """
        cls._providers[name] = provider_class

    @classmethod
    def create(
        cls,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMProvider:
        """Create a provider instance.

        Args:
            provider: Provider name
            model: Model identifier
            api_key: API key
            base_url: Base URL for API
            **kwargs: Additional configuration

        Returns:
            Configured provider instance

        Raises:
            ValueError: If provider is not registered
        """
        if provider not in cls._providers:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Available providers: {list(cls._providers.keys())}"
            )

        provider_class = cls._providers[provider]
        return provider_class(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered providers."""
        return list(cls._providers.keys())
