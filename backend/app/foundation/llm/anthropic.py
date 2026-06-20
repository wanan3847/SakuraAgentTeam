"""Anthropic LLM Provider implementation."""

from typing import Any, AsyncIterator, Iterator, List, Optional

from anthropic import Anthropic, AsyncAnthropic

from app.core.logging import get_logger
from app.foundation.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
)

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic provider implementation.

    Supports Claude 4 Opus, Claude 4 Sonnet, and other Claude models.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize Anthropic provider.

        Args:
            model: Model name (default: claude-sonnet-4-20250514)
            api_key: Anthropic API key
            base_url: Base URL for API (for proxies)
            **kwargs: Additional configuration
        """
        super().__init__(model, api_key, base_url, **kwargs)

        self.client = Anthropic(api_key=api_key, base_url=base_url)
        self.async_client = AsyncAnthropic(api_key=api_key, base_url=base_url)

    def _prepare_messages_for_anthropic(
        self, messages: List[Message]
    ) -> tuple[Optional[str], List[dict]]:
        """Prepare messages for Anthropic API.

        Anthropic uses a separate 'system' parameter instead of system messages.

        Args:
            messages: List of Message objects

        Returns:
            Tuple of (system_prompt, messages)
        """
        system_prompt = None
        api_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content
            else:
                api_messages.append(msg.to_dict())

        return system_prompt, api_messages

    def chat(self, messages: List[Message], **kwargs: Any) -> LLMResponse:
        """Synchronous chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLM response
        """
        logger.debug("anthropic_chat_start", model=self.model, message_count=len(messages))

        system_prompt, api_messages = self._prepare_messages_for_anthropic(messages)

        # Anthropic requires max_tokens
        max_tokens = kwargs.pop("max_tokens", 4096)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=api_messages,
            **kwargs,
        )

        content = response.content[0].text

        logger.debug(
            "anthropic_chat_complete",
            model=self.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
        )

    async def achat(self, messages: List[Message], **kwargs: Any) -> LLMResponse:
        """Asynchronous chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Returns:
            LLM response
        """
        logger.debug("anthropic_achat_start", model=self.model, message_count=len(messages))

        system_prompt, api_messages = self._prepare_messages_for_anthropic(messages)

        max_tokens = kwargs.pop("max_tokens", 4096)

        response = await self.async_client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=api_messages,
            **kwargs,
        )

        content = response.content[0].text

        logger.debug(
            "anthropic_achat_complete",
            model=self.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
        )

    def stream(self, messages: List[Message], **kwargs: Any) -> Iterator[str]:
        """Streaming chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of response text
        """
        logger.debug("anthropic_stream_start", model=self.model)

        system_prompt, api_messages = self._prepare_messages_for_anthropic(messages)
        max_tokens = kwargs.pop("max_tokens", 4096)

        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=api_messages,
            **kwargs,
        ) as stream:
            for text in stream.text_stream:
                yield text

    async def astream(self, messages: List[Message], **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronous streaming chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of response text
        """
        logger.debug("anthropic_astream_start", model=self.model)

        system_prompt, api_messages = self._prepare_messages_for_anthropic(messages)
        max_tokens = kwargs.pop("max_tokens", 4096)

        async with self.async_client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=api_messages,
            **kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield text
