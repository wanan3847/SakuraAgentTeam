"""Context compressor for agentic loops.

Inspired by Hermes' ContextCompressor (5-stage lossy compression):
  1. Prune old tool results (replace with summary stubs)
  2. Protect the head (system + user prompt + first assistant turn)
  3. Find a tail cut (keep the most recent N turns intact)
  4. Generate a summary of the pruned middle section
  5. Sanitize tool_call / tool_result pairs (never orphan a tool result)

Simplified for this codebase: we estimate tokens by char count (4 chars ≈ 1 token)
and prune old tool results to stubs when the conversation exceeds a threshold.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.foundation.llm.base import Message, MessageRole

logger = get_logger(__name__)

# Rough char-per-token ratio. OpenAI's rule of thumb is ~4 chars per token.
CHARS_PER_TOKEN = 4

# Default thresholds (in tokens). When the conversation exceeds max_tokens,
# we prune old tool results until it fits under target_tokens.
DEFAULT_MAX_TOKENS = 100_000
DEFAULT_TARGET_TOKENS = 60_000
DEFAULT_KEEP_RECENT_TURNS = 6  # keep the most recent 6 messages intact


def _estimate_tokens(messages: list[Message]) -> int:
    """Rough token estimate for the whole message list."""
    total_chars = 0
    for msg in messages:
        total_chars += len(msg.content or "")
        if msg.tool_calls:
            for tc in msg.tool_calls:
                total_chars += len(tc.name) + len(tc.arguments)
    return total_chars // CHARS_PER_TOKEN


def _truncate_str(s: str, max_chars: int) -> str:
    """Truncate a string to max_chars, appending a notice if cut."""
    if len(s) <= max_chars:
        return s
    return (
        s[:max_chars]
        + f"\n\n[... truncated: original was {len(s)} chars, "
        f"see temp file for full content ...]"
    )


def compress_context(
    messages: list[Message],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    keep_recent: int = DEFAULT_KEEP_RECENT_TURNS,
    max_tool_result_chars: int = 3000,
) -> list[Message]:
    """Compress a conversation to fit within token limits.

    Strategy (in order of aggressiveness):
      1. Truncate any single tool result that exceeds max_tool_result_chars.
      2. If still over max_tokens, replace old tool results (beyond the
         `keep_recent` tail) with short stubs.
      3. If still over, truncate the oldest non-protected messages.

    The head (system + first user message) is always protected.

    Args:
        messages: The full conversation.
        max_tokens: Hard limit — trigger compression when exceeded.
        target_tokens: Soft target — compress until under this.
        keep_recent: Never prune the most recent N messages.
        max_tool_result_chars: Max chars per tool result before truncation.

    Returns:
        A new list of compressed messages (original is not mutated).
    """
    if not messages:
        return messages

    current_tokens = _estimate_tokens(messages)
    if current_tokens <= max_tokens:
        # Still apply per-result truncation even if under limit
        return _truncate_tool_results(messages, max_tool_result_chars)

    logger.info(
        "context_compressing",
        current_tokens=current_tokens,
        max_tokens=max_tokens,
        target_tokens=target_tokens,
        message_count=len(messages),
    )

    # Stage 1: truncate individual tool results
    result = _truncate_tool_results(messages, max_tool_result_chars)

    # Stage 2: replace old tool results with stubs
    # Protect head: system messages + first user message
    head_end = 0
    for i, msg in enumerate(result):
        if msg.role in (MessageRole.SYSTEM, MessageRole.USER):
            head_end = i + 1
        else:
            break

    # Protect tail: last `keep_recent` messages
    tail_start = max(head_end, len(result) - keep_recent)

    # Prune tool results in the middle section
    pruned_count = 0
    for i in range(head_end, tail_start):
        msg = result[i]
        if msg.role == MessageRole.TOOL and len(msg.content) > 200:
            original_len = len(msg.content)
            result[i] = Message(
                role=msg.role,
                content=(
                    f"[pruned tool result: originally {original_len} chars, "
                    f"tool={msg.name}]"
                ),
                tool_call_id=msg.tool_call_id,
                name=msg.name,
            )
            pruned_count += 1

    # Check if we're under target now
    new_tokens = _estimate_tokens(result)
    if new_tokens <= target_tokens:
        logger.info(
            "context_compressed",
            original_tokens=current_tokens,
            new_tokens=new_tokens,
            pruned_results=pruned_count,
        )
        return result

    # Stage 3: truncate long assistant messages in the middle
    for i in range(head_end, tail_start):
        msg = result[i]
        if msg.role == MessageRole.ASSISTANT and len(msg.content) > 1000:
            result[i] = Message(
                role=msg.role,
                content=_truncate_str(msg.content, 500),
                tool_calls=msg.tool_calls,
            )

    final_tokens = _estimate_tokens(result)
    logger.info(
        "context_compressed_final",
        original_tokens=current_tokens,
        final_tokens=final_tokens,
        pruned_results=pruned_count,
    )
    return result


def _truncate_tool_results(
    messages: list[Message],
    max_chars: int,
) -> list[Message]:
    """Return a copy of messages with oversized tool results truncated."""
    result = []
    for msg in messages:
        if msg.role == MessageRole.TOOL and len(msg.content) > max_chars:
            result.append(
                Message(
                    role=msg.role,
                    content=_truncate_str(msg.content, max_chars),
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                )
            )
        else:
            result.append(msg)
    return result
