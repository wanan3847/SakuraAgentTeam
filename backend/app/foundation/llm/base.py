"""LLM Provider abstraction layer.

This module provides a unified interface for different LLM providers,
supporting OpenAI, Anthropic, and local models.

Function calling support:
- Message carries optional `tool_calls` (assistant messages) and
  `tool_call_id` / `name` (tool result messages).
- LLMResponse carries optional `tool_calls` parsed from the provider response.
- achat()/chat() accept a `tools` kwarg containing OpenAI-style function schemas.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MessageRole(StrEnum):
    """Message role in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """A single tool/function call requested by the LLM.

    Attributes:
        id: Provider-assigned id used to correlate the tool result.
        name: Name of the tool to call.
        arguments: JSON-encoded arguments string (per OpenAI spec).
    """

    id: str
    name: str
    arguments: str  # JSON string per OpenAI spec

    def parsed_arguments(self) -> dict[str, Any]:
        """Parse the JSON arguments string into a dict.

        Returns {} on parse failure.
        """
        import json

        try:
            return json.loads(self.arguments) if self.arguments else {}
        except Exception:
            return {}


@dataclass
class Message:
    """A single message in the conversation.

    For assistant messages that request tool calls, set `tool_calls`.
    For tool result messages, set role=TOOL, content=result text, and
    `tool_call_id` to the corresponding call id.
    """

    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None  # tool name for tool result messages

    def to_dict(self) -> dict:
        """Convert to dictionary format for API calls.

        Handles OpenAI's format for tool calls and tool results.
        """
        d: dict[str, Any] = {"role": self.role.value, "content": self.content}

        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in self.tool_calls
            ]
            # OpenAI allows empty content for assistant messages with tool_calls
            if not self.content:
                d["content"] = None

        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id

        if self.name:
            d["name"] = self.name

        return d


@dataclass
class LLMResponse:
    """Response from LLM provider.

    Attributes:
        content: Text content of the response (may be empty when tool_calls present).
        model: Model name that produced the response.
        usage: Token usage dict (prompt_tokens, completion_tokens, total_tokens).
        finish_reason: Provider's finish reason (stop, tool_calls, length, etc.).
        tool_calls: Optional list of tool calls the model wants to execute.
    """

    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None

    @property
    def wants_tool_call(self) -> bool:
        """True if the model requested one or more tool calls."""
        return bool(self.tool_calls)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    This class defines the unified interface that all LLM providers must implement.
    Inspired by OpenHands SDK and Claude Code Tool abstraction.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
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
    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """Synchronous chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, tools, etc.)

        Returns:
            LLM response
        """
        ...

    @abstractmethod
    async def achat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """Asynchronous chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters (supports `tools` for function calling)

        Returns:
            LLM response
        """
        ...

    @abstractmethod
    def stream(self, messages: list[Message], **kwargs: Any) -> Iterator[str]:
        """Streaming chat completion."""
        ...

    @abstractmethod
    async def astream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronous streaming chat completion."""
        ...

    def _prepare_messages(self, messages: list[Message]) -> list[dict]:
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
        api_key: str | None = None,
        base_url: str | None = None,
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
                f"Unknown provider: {provider}. Available providers: {list(cls._providers.keys())}"
            )

        provider_class = cls._providers[provider]
        return provider_class(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered providers."""
        return list(cls._providers.keys())
