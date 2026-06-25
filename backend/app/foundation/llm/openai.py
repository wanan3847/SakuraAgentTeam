"""OpenAI LLM Provider implementation.

Supports GPT-4, GPT-4o, GPT-3.5-turbo, and compatible APIs.
Includes function-calling (tools) support for agentic loops.
"""

from collections.abc import AsyncIterator, Iterator
from typing import Any

from openai import AsyncOpenAI, OpenAI

from app.core.logging import get_logger
from app.foundation.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    ToolCall,
)

logger = get_logger(__name__)


def _parse_tool_calls(message: Any) -> list[ToolCall] | None:
    """Extract ToolCall list from an OpenAI ChatCompletionMessage.

    Returns None if the message has no tool calls.
    """
    raw_calls = getattr(message, "tool_calls", None)
    if not raw_calls:
        return None
    result: list[ToolCall] = []
    for tc in raw_calls:
        func = getattr(tc, "function", None)
        if func is None:
            continue
        result.append(
            ToolCall(
                id=tc.id,
                name=func.name,
                arguments=func.arguments or "{}",
            )
        )
    return result or None


def _split_kwargs(kwargs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split kwargs into (provider_kwargs, passthrough_kwargs).

    - provider_kwargs: keys the OpenAI chat.completions.create() understands
      (tools, tool_choice, temperature, max_tokens, top_p, etc.)
    - passthrough_kwargs: keys we consume ourselves (session_id, agent_role)
    """
    consumed = {"session_id", "agent_role"}
    provider: dict[str, Any] = {}
    passthrough: dict[str, Any] = {}
    for k, v in kwargs.items():
        if k in consumed:
            passthrough[k] = v
        else:
            provider[k] = v
    return provider, passthrough


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation.

    Supports GPT-4, GPT-4o, GPT-3.5-turbo, and compatible APIs.
    Pass `tools=[...]` to achat()/chat() to enable function calling.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ):
        """Initialize OpenAI provider.

        Args:
            model: Model name (default: gpt-4o)
            api_key: OpenAI API key
            base_url: Base URL for API (for proxies or Azure)
            **kwargs: Additional configuration
        """
        super().__init__(model, api_key, base_url, **kwargs)

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """Synchronous chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, tools, etc.)

        Returns:
            LLM response
        """
        logger.debug("openai_chat_start", model=self.model, message_count=len(messages))

        provider_kwargs, _ = _split_kwargs(kwargs)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            **provider_kwargs,
        )

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = _parse_tool_calls(choice.message)

        logger.debug(
            "openai_chat_complete",
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            has_tool_calls=bool(tool_calls),
        )

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )

    async def achat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """Asynchronous chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters (supports `tools` for function calling)

        Returns:
            LLM response
        """
        logger.debug("openai_achat_start", model=self.model, message_count=len(messages))

        provider_kwargs, _ = _split_kwargs(kwargs)

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            **provider_kwargs,
        )

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = _parse_tool_calls(choice.message)

        logger.debug(
            "openai_achat_complete",
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            has_tool_calls=bool(tool_calls),
        )

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )

    def stream(self, messages: list[Message], **kwargs: Any) -> Iterator[str]:
        """Streaming chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of the response text
        """
        logger.debug("openai_stream_start", model=self.model)

        provider_kwargs, _ = _split_kwargs(kwargs)

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            stream=True,
            **provider_kwargs,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def astream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronous streaming chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of the response text
        """
        logger.debug("openai_astream_start", model=self.model)

        provider_kwargs, _ = _split_kwargs(kwargs)

        stream = await self.async_client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            stream=True,
            **provider_kwargs,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
