"""LiteLLM Provider — 通过 litellm 统一访问 100+ LLM 提供商。

litellm 在内部已经对接了：
  OpenAI / Anthropic / Google Gemini / Vertex AI / AWS Bedrock / Azure OpenAI /
  Mistral / Cohere / Groq / Together / OpenRouter / AI21 / HuggingFace /
  Ollama (本地) / vLLM (本地) / DeepSeek / Qwen (DashScope) / Zhipu GLM /
  月之暗面 Moonshot / 零一万物 / 火山引擎 / 腾讯混元 / 百度千帆 / 阿里云灵积 / …
  共 2784+ 个模型。

Model 命名规则（litellm 约定）：
  openai/gpt-4o
  anthropic/claude-3-5-sonnet-20241022
  bedrock/anthropic.claude-3-sonnet-20240229-v1:0
  vertex_ai/gemini-1.5-pro
  ollama/llama3
  deepseek/deepseek-chat
  openrouter/anthropic/claude-3-opus
  …

API Key 通过环境变量或 kwargs 传入：
  OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / HUGGINGFACE_API_KEY / …
  或在 create() 时通过 api_key 显式传入（落到 litellm 内部对应 provider 的 env）。

详细列表：https://docs.litellm.ai/docs/providers
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from app.core.logging import get_logger
from app.foundation.llm.base import LLMProvider, LLMResponse, Message

logger = get_logger(__name__)


class LiteLLMProvider(LLMProvider):
    """LiteLLM Provider — 100+ 提供商统一接口。

    用法：
        # 1. 走默认 provider（OpenAI 兼容协议）
        provider = LiteLLMProvider(model="gpt-4o", api_key="sk-...")

        # 2. 显式指定 litellm provider 前缀
        provider = LiteLLMProvider(
            model="anthropic/claude-3-5-sonnet-20241022",
            api_key="sk-ant-...",
        )

        # 3. 本地 Ollama
        provider = LiteLLMProvider(
            model="ollama/llama3",
            api_key="ollama",  # Ollama 不需要真 key，填占位
            base_url="http://localhost:11434",
        )

        # 4. 通过 base_url 自定义 OpenAI 兼容端点（vLLM、LMStudio 等）
        provider = LiteLLMProvider(
            model="custom-model",
            api_key="any",
            base_url="http://localhost:8000/v1",
        )
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(model, api_key, base_url, **kwargs)
        # 静默 litellm 的 INFO 级别日志（默认打太多）
        try:
            import litellm

            litellm.suppress_debug_info = True
        except ImportError:
            pass

    def _completion_kwargs(self, messages: list[Message], **kwargs: Any) -> dict[str, Any]:
        """构造 litellm.completion 调用参数。"""
        params: dict[str, Any] = {
            "model": self.model,
            "messages": self._prepare_messages(messages),
        }
        if self.api_key:
            params["api_key"] = self.api_key
        if self.base_url:
            params["api_base"] = self.base_url
        # 透传额外配置（temperature, max_tokens, top_p, stop, response_format 等）
        for k, v in self.config.items():
            params[k] = v
        params.update(kwargs)
        return params

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """同步 chat completion。"""
        import litellm

        logger.debug("litellm_chat_start", model=self.model, message_count=len(messages))
        params = self._completion_kwargs(messages, **kwargs)
        response = litellm.completion(**params)

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
            }
        return LLMResponse(
            content=content,
            model=getattr(response, "model", self.model),
            usage=usage,
            finish_reason=getattr(choice, "finish_reason", None),
        )

    async def achat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        """异步 chat completion。"""
        import litellm

        logger.debug("litellm_achat_start", model=self.model, message_count=len(messages))
        params = self._completion_kwargs(messages, **kwargs)
        response = await litellm.acompletion(**params)

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
            }
        return LLMResponse(
            content=content,
            model=getattr(response, "model", self.model),
            usage=usage,
            finish_reason=getattr(choice, "finish_reason", None),
        )

    def stream(self, messages: list[Message], **kwargs: Any) -> Iterator[str]:
        """同步流式 chat completion。"""
        import litellm

        logger.debug("litellm_stream_start", model=self.model)
        params = self._completion_kwargs(messages, stream=True, **kwargs)
        response = litellm.completion(**params)
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def astream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[str]:
        """异步流式 chat completion。"""
        import litellm

        logger.debug("litellm_astream_start", model=self.model)
        params = self._completion_kwargs(messages, stream=True, **kwargs)
        response = await litellm.acompletion(**params)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ============================================================
# 实用工具：列常见模型 / 解析 model 名
# ============================================================


# 常用 provider 速查（不依赖 litellm 实际加载）
COMMON_PROVIDERS = [
    # 协议类
    ("openai", "OpenAI（gpt-4o / gpt-4-turbo / o1 / o3 …）"),
    ("anthropic", "Anthropic（claude-3-5-sonnet / claude-3-opus …）"),
    # 云平台
    ("bedrock", "AWS Bedrock（Claude / Llama / Titan / Mistral on AWS）"),
    ("vertex_ai", "Google Vertex AI（Gemini / Claude / Llama on GCP）"),
    ("azure", "Azure OpenAI"),
    # 国产
    ("deepseek", "DeepSeek（deepseek-chat / deepseek-coder / deepseek-reasoner）"),
    ("dashscope", "阿里云通义千问 Qwen（qwen-plus / qwen-max / qwen-coder）"),
    ("zhipuai", "智谱 GLM（glm-4 / glm-4-plus）"),
    ("moonshot", "月之暗面 Kimi（moonshot-v1-128k）"),
    ("yi", "零一万物（yi-large / yi-medium）"),
    ("volcengine", "火山引擎（豆包）"),
    ("hunyuan", "腾讯混元"),
    ("qianfan", "百度千帆"),
    # 主流第三方
    ("gemini", "Google Gemini（gemini-1.5-pro / gemini-2.0-flash）"),
    ("mistral", "Mistral（mistral-large / mixtral / codestral）"),
    ("cohere", "Cohere（command-r-plus）"),
    ("groq", "Groq（超快推理，llama3 / mixtral on Groq）"),
    ("together_ai", "Together AI（开源模型托管）"),
    ("openrouter", "OpenRouter（统一路由 100+ 模型）"),
    ("fireworks_ai", "Fireworks AI"),
    ("deepinfra", "DeepInfra"),
    # 本地
    ("ollama", "Ollama（本地 llama3 / qwen / mistral）"),
    ("vllm", "vLLM（本地部署的 OpenAI 兼容）"),
    ("openai_like", "任意 OpenAI 兼容端点（用 base_url 指定）"),
]


def list_common_providers() -> list[dict[str, str]]:
    """列出常用 provider 及说明（用于 CLI doctor / docs）。"""
    return [{"prefix": p, "description": d} for p, d in COMMON_PROVIDERS]


def normalize_model_name(model: str, default_provider: str = "openai") -> str:
    """把短模型名补全为 litellm 完整名（"gpt-4o" → "openai/gpt-4o"）。

    已包含 "/" 的（"openai/gpt-4o", "ollama/llama3"）原样返回。
    """
    if "/" in model:
        return model
    return f"{default_provider}/{model}"
