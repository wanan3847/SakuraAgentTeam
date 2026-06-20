"""OpenAI LLM Provider implementation."""

from typing import Any, AsyncIterator, Iterator, List, Optional

from openai import OpenAI, AsyncOpenAI

from app.core.logging import get_logger
from app.foundation.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
)

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation.

    Supports GPT-4, GPT-4o, GPT-3.5-turbo, and compatible APIs.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
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

    def chat(self, messages: List[Message], **kwargs: Any) -> LLMResponse:
        """Synchronous chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLM response
        """
        logger.debug("openai_chat_start", model=self.model, message_count=len(messages))

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            **kwargs,
        )

        content = response.choices[0].message.content or ""

        logger.debug(
            "openai_chat_complete",
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    async def achat(self, messages: List[Message], **kwargs: Any) -> LLMResponse:
        """Asynchronous chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Returns:
            LLM response
        """
        logger.debug("openai_achat_start", model=self.model, message_count=len(messages))

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            **kwargs,
        )

        content = response.choices[0].message.content or ""

        logger.debug(
            "openai_achat_complete",
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    def stream(self, messages: List[Message], **kwargs: Any) -> Iterator[str]:
        """Streaming chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of response text
        """
        logger.debug("openai_stream_start", model=self.model)

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            stream=True,
            **kwargs,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def astream(self, messages: List[Message], **kwargs: Any) -> AsyncIterator[str]:
        """Asynchronous streaming chat completion.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters

        Yields:
            Chunks of response text
        """
        logger.debug("openai_astream_start", model=self.model)

        stream = await self.async_client.chat.completions.create(
            model=self.model,
            messages=self._prepare_messages(messages),
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
