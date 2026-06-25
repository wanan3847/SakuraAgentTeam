"""LLM token & cost metering.

Wraps any LLMProvider to accumulate token usage and cost per session/agent/model.
Inspired by Claude Code's token tracking and Hermes cost awareness.
"""

import threading
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.foundation.llm.base import LLMProvider, LLMResponse, Message

logger = get_logger(__name__)


@dataclass
class UsageRecord:
    """Single LLM call usage record."""

    session_id: str
    agent_role: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    duration_ms: float = 0.0


@dataclass
class SessionUsage:
    """Aggregated usage for a session."""

    session_id: str
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    by_agent: dict[str, dict[str, int | float]] = field(default_factory=dict)
    by_model: dict[str, dict[str, int | float]] = field(default_factory=dict)
    records: list[UsageRecord] = field(default_factory=list)

    def add(self, record: UsageRecord) -> None:
        self.total_prompt_tokens += record.prompt_tokens
        self.total_completion_tokens += record.completion_tokens
        self.total_tokens += record.total_tokens
        self.total_cost_usd += record.cost_usd
        self.call_count += 1
        self.records.append(record)

        agent_key = record.agent_role
        if agent_key not in self.by_agent:
            self.by_agent[agent_key] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "calls": 0,
            }
        a = self.by_agent[agent_key]
        a["prompt_tokens"] += record.prompt_tokens
        a["completion_tokens"] += record.completion_tokens
        a["total_tokens"] += record.total_tokens
        a["cost_usd"] += record.cost_usd
        a["calls"] += 1

        model_key = record.model
        if model_key not in self.by_model:
            self.by_model[model_key] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "calls": 0,
            }
        m = self.by_model[model_key]
        m["prompt_tokens"] += record.prompt_tokens
        m["completion_tokens"] += record.completion_tokens
        m["total_tokens"] += record.total_tokens
        m["cost_usd"] += record.cost_usd
        m["calls"] += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "call_count": self.call_count,
            "by_agent": dict(self.by_agent),
            "by_model": dict(self.by_model),
        }


# Pricing table (USD per 1K tokens). Falls back to 0 if unknown.
# Covers common models; litellm has more but this avoids runtime dep.
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-5.4-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-5.3-codex": {"input": 0.0015, "output": 0.006},
    "gpt-5.2": {"input": 0.0025, "output": 0.01},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},
    "qwen3.7-max": {"input": 0.002, "output": 0.006},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD for a single call."""
    # Strip provider prefix: "openai/gpt-4o" -> "gpt-4o"
    short = model.split("/")[-1] if "/" in model else model
    pricing = PRICING.get(short)
    if not pricing:
        # Try partial match
        for key, val in PRICING.items():
            if key in short or short in key:
                pricing = val
                break
    if not pricing:
        return 0.0
    return (prompt_tokens / 1000.0) * pricing["input"] + (completion_tokens / 1000.0) * pricing["output"]


class MeteredLLMProvider:
    """Wraps an LLMProvider to track token usage and cost.

    Thread-safe. Stores per-session aggregates that the CLI/API can read.
    """

    def __init__(self, inner: LLMProvider):
        self._inner = inner
        self._sessions: dict[str, SessionUsage] = {}
        self._lock = threading.Lock()

    @property
    def model(self) -> str:
        return self._inner.model

    def get_session_usage(self, session_id: str) -> SessionUsage:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionUsage(session_id=session_id)
            return self._sessions[session_id]

    def reset_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _record(
        self,
        session_id: str,
        agent_role: str,
        response: LLMResponse,
        duration_ms: float = 0.0,
    ) -> UsageRecord:
        usage = response.usage or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens))
        cost = estimate_cost(response.model, prompt_tokens, completion_tokens)

        record = UsageRecord(
            session_id=session_id,
            agent_role=agent_role,
            model=response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
        )

        session_usage = self.get_session_usage(session_id)
        with self._lock:
            session_usage.add(record)

        logger.info(
            "llm_token_used",
            session_id=session_id,
            agent_role=agent_role,
            model=response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost, 6),
        )
        return record

    def chat(
        self,
        messages: list[Message],
        *,
        session_id: str = "",
        agent_role: str = "",
        **kwargs: Any,
    ) -> LLMResponse:
        import time

        t0 = time.perf_counter()
        resp = self._inner.chat(messages, **kwargs)
        duration_ms = (time.perf_counter() - t0) * 1000
        if session_id:
            self._record(session_id, agent_role, resp, duration_ms)
        return resp

    async def achat(
        self,
        messages: list[Message],
        *,
        session_id: str = "",
        agent_role: str = "",
        **kwargs: Any,
    ) -> LLMResponse:
        import time

        t0 = time.perf_counter()
        resp = await self._inner.achat(messages, **kwargs)
        duration_ms = (time.perf_counter() - t0) * 1000
        if session_id:
            self._record(session_id, agent_role, resp, duration_ms)
        return resp

    def stream(self, messages: list[Message], **kwargs: Any):
        return self._inner.stream(messages, **kwargs)

    async def astream(self, messages: list[Message], **kwargs: Any):
        async for chunk in self._inner.astream(messages, **kwargs):
            yield chunk


# Global metered provider (set by create_default_engine or CLI)
_global_metered: MeteredLLMProvider | None = None


def set_global_provider(provider: MeteredLLMProvider) -> None:
    global _global_metered
    _global_metered = provider


def get_global_provider() -> MeteredLLMProvider | None:
    return _global_metered
