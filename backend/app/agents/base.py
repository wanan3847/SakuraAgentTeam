"""Agent base class defining the unified lifecycle.

Inspired by Claude Code's Coordinator pattern + OpenHands's Agent abstraction.

Each Agent follows the same lifecycle:
  1. plan(ctx)    -> Plan      # Analyze context, create execution plan
  2. execute(plan, ctx) -> Artifact  # Execute plan steps
  3. review(artifact, ctx) -> ReviewResult  # Self-review output

Subclasses implement the specific logic for their role.
"""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.agents.types import (
    AgentRole,
    AgentStatus,
    Artifact,
    Context,
    Plan,
    PlanStep,
    TeamMessage,
)
from app.core.logging import get_logger
from app.foundation.llm.base import LLMProvider, LLMResponse, Message, MessageRole, ToolCall
from app.foundation.tools import tool_registry
from app.foundation.tools.base import Tool, ToolResult

logger = get_logger(__name__)


@dataclass
class ReviewResult:
    """Result of an Agent's self-review."""

    passed: bool
    issues: list[str]
    suggestions: list[str]


class Agent(ABC):
    """Abstract base class for all Agents.

    Provides the unified lifecycle interface (plan -> execute -> review)
    and shared utilities (LLM calls, tool execution, logging).
    """

    role: AgentRole
    description: str = ""
    system_prompt: str = ""
    skills: list[str] = field(default_factory=list)

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        tools: dict[str, Any] | None = None,
    ):
        """Initialize the Agent.

        Args:
            llm_provider: LLM provider for LLM-based reasoning
            tools: Available tools (inherited from registry)
        """
        self.llm = llm_provider
        self.tools = tools or {}
        self.status: AgentStatus = AgentStatus.PENDING
        self.current_plan: Plan | None = None
        self.last_artifact: Artifact | None = None

    async def plan(self, ctx: Context) -> Plan:
        """Create an execution plan based on the shared context.

        Default: Ask LLM to break the task into steps.
        Subclasses may override with role-specific planning logic.
        """
        self.status = AgentStatus.RUNNING
        logger.info("agent_planning", agent_role=self.role.value)

        # Build prompt for planning
        previous_outputs = []
        for role, output in ctx.agent_outputs.items():
            if isinstance(output, Artifact):
                previous_outputs.append(f"- {role}: {output.artifact_type} - {output.name}")
            else:
                previous_outputs.append(f"- {role}: {type(output).__name__}")

        f"""You are the {self.role.value} agent in a multi-agent workflow.

## Your Role
{self.description or self._default_description()}

## User Requirement
{ctx.user_requirement}

## Previous Agent Outputs
{"No previous outputs yet (first agent in the chain)" if not previous_outputs else chr(10).join(previous_outputs)}

## Experience Hints (lessons from past)
{chr(10).join(f"- {h['content']}" for h in ctx.experience_hints) if ctx.experience_hints else "No past experiences"}

## Task
Create a plan with 2-5 steps to complete your part of the work.
Return your response as a JSON object:
{{
  "summary": "brief description of what you will do",
  "steps": [
    {{
      "description": "Step description",
      "tool": "name_of_tool",
      "parameters": {{ ... }}
    }}
  ]
}}"""

        plan = Plan(agent_role=self.role.value, summary="")

        # For now, provide a default plan if LLM not available
        # In production this uses the LLM planning prompt
        plan.summary = self._default_plan_summary(ctx)
        for step in self._default_plan_steps(ctx):
            plan.steps.append(step)

        self.current_plan = plan
        logger.info(
            "agent_plan_created",
            agent_role=self.role.value,
            steps_count=len(plan.steps),
        )

        return plan

    @abstractmethod
    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Execute the plan and produce an artifact.

        This method contains the role-specific logic.
        """
        ...

    async def review(self, artifact: Artifact, ctx: Context) -> ReviewResult:
        """Self-review the generated artifact.

        Default: Always passes. Subclasses should implement actual checks.
        """
        logger.info("agent_reviewing", agent_role=self.role.value)

        # Default checks: verify artifact has content
        issues = []
        suggestions = []

        if not artifact.content or len(str(artifact.content).strip()) < 50:
            issues.append("Content appears too short")

        # TODO: Use LLM for deeper review in production

        passed = len(issues) == 0

        if passed:
            self.status = AgentStatus.COMPLETED
        else:
            self.status = AgentStatus.FAILED

        logger.info(
            "agent_review_complete",
            agent_role=self.role.value,
            passed=passed,
            issues_count=len(issues),
        )

        return ReviewResult(
            passed=passed,
            issues=issues,
            suggestions=suggestions,
        )

    async def run(self, ctx: Context) -> Artifact:
        """Full agent lifecycle: plan -> execute -> review."""
        logger.info(
            "agent_starting",
            agent_role=self.role.value,
            session_id=ctx.session_id,
        )

        # 1. Plan
        plan = await self.plan(ctx)

        # 1.5 接收团队消息，注入到上下文供 execute 使用
        inbox = await self.receive_messages(ctx)
        if inbox:
            inbox_text = "\n".join(
                f"[{m.message_type}] from {m.from_role}: {m.content}"
                for m in inbox
            )
            ctx.metadata[f"team_inbox_{self.role.value}"] = inbox_text
            logger.info(
                "agent_inbox",
                agent_role=self.role.value,
                messages_count=len(inbox),
            )

        # 2. Execute
        artifact = await self.execute(plan, ctx)
        self.last_artifact = artifact

        # 3. Review
        review = await self.review(artifact, ctx)

        if not review.passed:
            logger.warning(
                "agent_review_failed",
                agent_role=self.role.value,
                issues=review.issues,
            )

        # Register output in shared context
        ctx.set_output(self.role.value, artifact)

        # Persist changes to the project git repo so users can roll back.
        await self._commit_to_project_repo(ctx, artifact)

        logger.info(
            "agent_completed",
            agent_role=self.role.value,
            status=self.status.value,
        )

        return artifact

    # --- Team communication -------------------------------------------

    async def communicate(
        self,
        ctx: Context,
        to_role: str,
        message_type: str,
        content: str,
        **metadata: Any,
    ) -> TeamMessage:
        """发送消息给其他 agent。

        Args:
            ctx: 共享上下文
            to_role: 接收者 agent role ("all" = 广播)
            message_type: 消息类型 ("question" | "suggestion" | "review" | "handoff")
            content: 消息内容
            **metadata: 附加元数据

        Returns:
            创建的 TeamMessage
        """
        msg = ctx.send_message(
            from_role=self.role.value,
            to_role=to_role,
            message_type=message_type,
            content=content,
            **metadata,
        )
        logger.info(
            "agent_message_sent",
            from_role=self.role.value,
            to_role=to_role,
            message_type=message_type,
        )
        return msg

    async def receive_messages(self, ctx: Context) -> list[TeamMessage]:
        """接收发给本 agent 的消息（含广播消息）。"""
        return ctx.get_messages_to(self.role.value)

    # --- LLM helpers ---------------------------------------------------

    async def llm_chat(
        self,
        prompt: str,
        ctx: Context,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Call the LLM with a prompt and return the response text.

        Automatically:
        - Uses the agent's system_prompt if system_prompt is None
        - Records token usage via MeteredLLMProvider
        - Publishes an AGENT_LOG event with token info
        """
        if not self.llm:
            raise RuntimeError(
                f"Agent {self.role.value} has no LLM provider. "
                "Set llm_provider in __init__ or use template fallback."
            )

        messages: list[Message] = []
        sys_msg = system_prompt if system_prompt is not None else self.system_prompt
        if sys_msg:
            messages.append(Message(role=MessageRole.SYSTEM, content=sys_msg))
        messages.append(Message(role=MessageRole.USER, content=prompt))

        # Support both MeteredLLMProvider (has session_id/agent_role kwargs)
        # and raw LLMProvider
        try:
            from app.foundation.llm.meter import MeteredLLMProvider

            if isinstance(self.llm, MeteredLLMProvider):
                resp = await self.llm.achat(
                    messages,
                    session_id=ctx.session_id,
                    agent_role=self.role.value,
                    **kwargs,
                )
            else:
                resp = await self.llm.achat(messages, **kwargs)
        except Exception as exc:
            logger.error(
                "agent_llm_call_failed",
                agent_role=self.role.value,
                error=str(exc),
            )
            raise

        # Publish token usage as an agent log event
        usage = resp.usage or {}
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)
        total_t = usage.get("total_tokens", prompt_t + completion_t)

        # Try to publish event via EventBus (non-blocking, best-effort)
        try:
            from app.orchestration.eventbus import EventBus, Event, EventType

            # Find the global event bus
            import app.orchestration.eventbus as _eb_mod

            bus: EventBus = _eb_mod.event_bus
            await bus.publish(
                Event(
                    event_type=EventType.AGENT_LOG.value,
                    session_id=ctx.session_id,
                    payload={
                        "agent_role": self.role.value,
                        "message": f"LLM call: {prompt_t}+{completion_t}={total_t} tokens",
                        "level": "info",
                        "token_usage": {
                            "prompt_tokens": prompt_t,
                            "completion_tokens": completion_t,
                            "total_tokens": total_t,
                            "model": resp.model,
                        },
                    },
                )
            )
        except Exception:
            pass  # EventBus not available, skip

        logger.info(
            "agent_llm_called",
            agent_role=self.role.value,
            model=resp.model,
            prompt_tokens=prompt_t,
            completion_tokens=completion_t,
            total_tokens=total_t,
        )

        return resp.content

    # --- Agentic loop (LLM <-> tools) ---------------------------------

    # Config knobs for the agentic loop (class-level, overridable per agent)
    AGENTIC_MAX_TOKENS: int = 100_000
    AGENTIC_TARGET_TOKENS: int = 60_000
    AGENTIC_MAX_TOOL_RESULT_CHARS: int = 8000

    async def run_agentic_loop(
        self,
        prompt: str,
        ctx: Context,
        system_prompt: str | None = None,
        tools: list[Tool] | None = None,
        max_iterations: int = 15,
        on_iteration: Any = None,
        on_tool_call: Any = None,
        on_tool_result: Any = None,
        on_llm_response: Any = None,
        **kwargs: Any,
    ) -> str:
        """Run an agentic loop: LLM <-> tools until the LLM produces a final answer.

        Inspired by Claude Code's agent loop and Hermes' conversation_loop:
            1. Send messages + tool schemas to the LLM.
            2. If the LLM returns tool_calls, execute them (concurrently) and
               feed results back.
            3. Repeat until the LLM returns no tool_calls (final answer) or
               max_iterations is reached.
            4. Compress context when it exceeds the token budget.

        Callbacks (all optional, called for real-time UI updates):
            on_iteration(iteration: int, message_count: int)
            on_tool_call(tool_name: str, arguments: str)
            on_tool_result(tool_name: str, success: bool, output_preview: str)
            on_llm_response(content: str, has_tool_calls: bool)

        Args:
            prompt: The user's task prompt.
            ctx: Shared context (for session_id, project paths, etc.).
            system_prompt: Optional system prompt override.
            tools: Tools the LLM may call. Defaults to all registered tools.
            max_iterations: Safety cap on LLM round-trips.
            **kwargs: Extra kwargs forwarded to the LLM (temperature, etc.).

        Returns:
            The final text response from the LLM.
        """
        if not self.llm:
            raise RuntimeError(
                f"Agent {self.role.value} has no LLM provider; cannot run agentic loop."
            )

        # Resolve tools
        if tools is None:
            tools = tool_registry.get_all_tools()
        tool_schemas = [t.to_function_schema() for t in tools] if tools else []
        tool_map: dict[str, Tool] = {t.name: t for t in tools}

        # Build the initial message list
        sys_msg = system_prompt if system_prompt is not None else self.system_prompt
        messages: list[Message] = []
        if sys_msg:
            messages.append(Message(role=MessageRole.SYSTEM, content=sys_msg))
        messages.append(Message(role=MessageRole.USER, content=prompt))

        # Build the execution context for tools
        tool_ctx = self._build_tool_context(ctx)

        final_content = ""
        for iteration in range(1, max_iterations + 1):
            logger.info(
                "agentic_loop_iteration",
                agent_role=self.role.value,
                iteration=iteration,
                message_count=len(messages),
            )
            if on_iteration:
                try:
                    on_iteration(iteration, len(messages))
                except Exception:
                    pass

            # Compress context if it's getting too long
            messages = self._maybe_compress_context(messages)

            # Call the LLM with tools enabled
            call_kwargs: dict[str, Any] = dict(kwargs)
            if tool_schemas:
                call_kwargs["tools"] = tool_schemas
                # Let the model decide; don't force a tool call.
                call_kwargs.setdefault("tool_choice", "auto")

            resp = await self._call_llm_raw(messages, ctx, **call_kwargs)

            # Publish token usage (best-effort)
            self._publish_token_event(resp, ctx)

            if on_llm_response:
                try:
                    on_llm_response(resp.content or "", bool(resp.tool_calls))
                except Exception:
                    pass

            # If the LLM didn't request any tool call, we're done.
            if not resp.tool_calls:
                final_content = resp.content
                logger.info(
                    "agentic_loop_done",
                    agent_role=self.role.value,
                    iteration=iteration,
                    reason="no_tool_calls",
                )
                break

            # Append the assistant message (with tool_calls) to the conversation
            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=resp.content or "",
                    tool_calls=resp.tool_calls,
                )
            )

            # Execute tool calls concurrently (Hermes-style parallel dispatch)
            tool_results = await self._execute_tool_calls_concurrent(
                resp.tool_calls, tool_map, tool_ctx, on_tool_call, on_tool_result
            )

            # Append each tool result as a separate message
            for tc, result in zip(resp.tool_calls, tool_results):
                messages.append(
                    Message(
                        role=MessageRole.TOOL,
                        content=self._truncate_tool_output(result),
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

            # If this was the last allowed iteration, return whatever text we have.
            if iteration == max_iterations:
                final_content = resp.content or ""
                logger.warning(
                    "agentic_loop_max_iterations",
                    agent_role=self.role.value,
                    max_iterations=max_iterations,
                )
                break
        else:
            # Loop exited without break (shouldn't happen, but be safe)
            final_content = final_content or ""

        return final_content

    def _maybe_compress_context(self, messages: list[Message]) -> list[Message]:
        """Compress the conversation if it exceeds the token budget.

        Uses the context_compressor module (inspired by Hermes ContextCompressor).
        """
        try:
            from app.foundation.llm.context_compressor import compress_context

            return compress_context(
                messages,
                max_tokens=self.AGENTIC_MAX_TOKENS,
                target_tokens=self.AGENTIC_TARGET_TOKENS,
                max_tool_result_chars=self.AGENTIC_MAX_TOOL_RESULT_CHARS,
            )
        except Exception as exc:
            logger.debug("context_compress_skipped", error=str(exc))
            return messages

    def _truncate_tool_output(self, result: ToolResult) -> str:
        """Truncate a tool result for the LLM if it's too large.

        Inspired by Claude Code: large results are written to a temp file
        and the LLM gets a preview + file path.
        """
        content = result.to_llm_content()
        max_chars = self.AGENTIC_MAX_TOOL_RESULT_CHARS
        if len(content) <= max_chars:
            return content

        # Write full result to a temp file
        import tempfile
        import os

        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                prefix=f"tool_{result.metadata.get('tool', 'result')}_",
                delete=False,
                encoding="utf-8",
            )
            tmp.write(content)
            tmp.close()
            preview = content[:max_chars]
            return (
                f"{preview}\n\n"
                f"[... output truncated: {len(content)} total chars. "
                f"Full output saved to: {tmp.name} ...]"
            )
        except Exception:
            # Fallback: just truncate inline
            return content[:max_chars] + f"\n\n[... truncated: {len(content)} chars ...]"

    async def _execute_tool_calls_concurrent(
        self,
        tool_calls: list[ToolCall],
        tool_map: dict[str, Tool],
        tool_ctx: dict[str, Any],
        on_tool_call: Any = None,
        on_tool_result: Any = None,
    ) -> list[ToolResult]:
        """Execute multiple tool calls concurrently.

        Hermes' tool_executor dispatches independent tool calls in parallel
        via a ThreadPoolExecutor. We use asyncio.gather for the same effect.
        """
        import asyncio

        async def _run_one(tc: ToolCall) -> ToolResult:
            if on_tool_call:
                try:
                    on_tool_call(tc.name, tc.arguments[:200])
                except Exception:
                    pass
            result = await self._execute_tool_call(tc, tool_map, tool_ctx)
            if on_tool_result:
                try:
                    on_tool_result(
                        tc.name,
                        result.success,
                        result.output[:200] if result.output else "",
                    )
                except Exception:
                    pass
            return result

        # If only one call, skip the gather overhead
        if len(tool_calls) == 1:
            return [await _run_one(tool_calls[0])]

        # Run all concurrently
        return await asyncio.gather(*[_run_one(tc) for tc in tool_calls])

    async def _call_llm_raw(
        self,
        messages: list[Message],
        ctx: Context,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the LLM provider with raw kwargs (supports tools)."""
        try:
            from app.foundation.llm.meter import MeteredLLMProvider

            if isinstance(self.llm, MeteredLLMProvider):
                return await self.llm.achat(
                    messages,
                    session_id=ctx.session_id,
                    agent_role=self.role.value,
                    **kwargs,
                )
        except Exception as exc:
            logger.error("agentic_llm_call_failed", agent_role=self.role.value, error=str(exc))
            raise
        return await self.llm.achat(messages, **kwargs)

    def _build_tool_context(self, ctx: Context) -> dict[str, Any]:
        """Build the context dict passed to tool.call()."""
        return {
            "session_id": ctx.session_id,
            "agent_role": self.role.value,
            "projects_root": ctx.metadata.get("projects_root") if ctx.metadata else None,
            "project_id": ctx.metadata.get("project_id") if ctx.metadata else None,
            "user_requirement": ctx.user_requirement,
        }

    async def _execute_tool_call(
        self,
        tc: ToolCall,
        tool_map: dict[str, Tool],
        tool_ctx: dict[str, Any],
    ) -> ToolResult:
        """Execute a single tool call requested by the LLM.

        Returns a ToolResult. Never raises — failures are returned as
        ToolResult(success=False, error=...) so the loop can feed the
        error back to the LLM.
        """
        tool = tool_map.get(tc.name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tc.name}. Available: {list(tool_map.keys())}",
            )

        try:
            input_data = tool.validate_input(tc.parsed_arguments())
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid arguments for {tc.name}: {e}",
            )

        try:
            logger.info(
                "tool_call_start",
                agent_role=self.role.value,
                tool=tc.name,
                arguments=tc.arguments[:500],
            )
            result = await tool.call(input_data, tool_ctx)
            logger.info(
                "tool_call_complete",
                agent_role=self.role.value,
                tool=tc.name,
                success=result.success,
                output_len=len(result.output),
            )
            return result
        except Exception as e:
            logger.error(
                "tool_call_exception",
                agent_role=self.role.value,
                tool=tc.name,
                error=str(e),
            )
            return ToolResult(
                success=False,
                output="",
                error=f"Tool {tc.name} raised: {e}",
            )

    def _publish_token_event(self, resp: LLMResponse, ctx: Context) -> None:
        """Best-effort publish of token usage to the EventBus."""
        try:
            from app.orchestration.eventbus import EventBus, Event, EventType
            import app.orchestration.eventbus as _eb_mod

            usage = resp.usage or {}
            prompt_t = usage.get("prompt_tokens", 0)
            completion_t = usage.get("completion_tokens", 0)
            total_t = usage.get("total_tokens", prompt_t + completion_t)

            bus: EventBus = _eb_mod.event_bus
            import asyncio

            asyncio.ensure_future(
                bus.publish(
                    Event(
                        event_type=EventType.AGENT_LOG.value,
                        session_id=ctx.session_id,
                        payload={
                            "agent_role": self.role.value,
                            "message": f"LLM call: {prompt_t}+{completion_t}={total_t} tokens",
                            "level": "info",
                            "token_usage": {
                                "prompt_tokens": prompt_t,
                                "completion_tokens": completion_t,
                                "total_tokens": total_t,
                                "model": resp.model,
                            },
                        },
                    )
                )
            )
        except Exception:
            pass  # EventBus not available, skip

    # --- System prompt construction (layered, Hermes-style) -----------

    def build_system_prompt(
        self,
        ctx: Context,
        tools: list[Tool] | None = None,
        extra_context: str = "",
    ) -> str:
        """Build a layered system prompt: identity + tools + context.

        Inspired by Hermes' three-layer system prompt:
        - stable: agent identity + role description
        - tools: available tool descriptions (so the LLM knows what it can call)
        - context: user requirement, previous agent outputs, experience hints

        Args:
            ctx: Shared context.
            tools: Tools to advertise. Defaults to all registered tools.
            extra_context: Extra context text appended at the end.

        Returns:
            A composed system prompt string.
        """
        if tools is None:
            tools = tool_registry.get_all_tools()

        parts: list[str] = []

        # --- Layer 1: Identity ---
        parts.append(f"# Role\nYou are the {self.role.value} agent in a multi-agent team.")
        if self.description:
            parts.append(f"\n{self.description}")
        else:
            parts.append(f"\n{self._default_description()}")

        # --- Layer 2: Tools ---
        if tools:
            parts.append("\n# Available Tools")
            parts.append(
                "You can call the following tools via function calling. "
                "Use them to inspect the codebase, read/write files, and run commands. "
                "Prefer tools over guessing file contents."
            )
            for t in tools:
                readonly_tag = " (read-only)" if t.is_readonly(t.input_schema()) else ""
                parts.append(f"- `{t.name}`{readonly_tag}: {t.description}")

        # --- Layer 3: Context ---
        parts.append("\n# Context")
        parts.append(f"\n## User Requirement\n{ctx.user_requirement}")

        # Previous agent outputs
        prev_lines: list[str] = []
        for role, output in ctx.agent_outputs.items():
            if isinstance(output, Artifact):
                prev_lines.append(
                    f"- {role}: {output.artifact_type} - {output.name} "
                    f"({len(str(output.content))} chars)"
                )
            else:
                prev_lines.append(f"- {role}: {type(output).__name__}")
        if prev_lines:
            parts.append("\n## Previous Agent Outputs\n" + "\n".join(prev_lines))
        else:
            parts.append("\n## Previous Agent Outputs\n(none — you are the first agent)")

        # Experience hints
        if ctx.experience_hints:
            hints = "\n".join(f"- {h['content']}" for h in ctx.experience_hints)
            parts.append(f"\n## Experience Hints\n{hints}")

        # Team inbox
        if ctx.metadata:
            inbox = ctx.metadata.get(f"team_inbox_{self.role.value}")
            if inbox:
                parts.append(f"\n## Team Messages\n{inbox}")

        # Extra context (caller-supplied)
        if extra_context:
            parts.append(f"\n# Extra Context\n{extra_context}")

        # Output format guidance
        parts.append(
            "\n# Output Format\n"
            "When you finish, return your final answer as plain text. "
            "If you produced files, list them using `### FILE: <path>` blocks "
            "followed by a fenced code block with the file content."
        )

        return "\n".join(parts)

    async def llm_generate_files(
        self,
        prompt: str,
        ctx: Context,
        required_files: list[str] | None = None,
        max_iterations: int = 15,
    ) -> dict[str, str]:
        """Run the agentic loop to generate files, then parse them.

        This is the agentic replacement for the old pattern:
            response = await self.llm_chat(prompt, ctx)
            files_map = self.parse_files_block(response)

        The agentic loop lets the LLM call tools (file_read, glob, grep) to
        inspect the codebase before generating code, producing much better
        output than a blind one-shot call.

        Args:
            prompt: The generation prompt (should include output format guidance).
            ctx: Shared context.
            required_files: If provided, raise ValueError when any of these
                files are missing from the LLM response.
            max_iterations: Max LLM round-trips in the agentic loop.

        Returns:
            A dict of {file_path: file_content}.

        Raises:
            ValueError: If required_files is set and any are missing.
            RuntimeError: If no LLM provider is configured.
        """
        system_prompt = self.build_system_prompt(ctx)
        response = await self.run_agentic_loop(
            prompt=prompt,
            ctx=ctx,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
        )
        files_map = self.parse_files_block(response)

        if required_files:
            missing = [f for f in required_files if f not in files_map or not files_map[f].strip()]
            if missing:
                raise ValueError(f"LLM 生成的文件不完整，缺少: {missing}")

        return files_map

    @staticmethod
    def parse_files_block(text: str) -> dict[str, str]:
        """Parse '### FILE: path\\n```code```' blocks from LLM response.

        Returns a dict of {file_path: file_content}.
        """
        pattern = r"### FILE:\s*([^\n]+)\s*```[a-zA-Z]*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return {path.strip(): content for path, content in matches}

    @staticmethod
    def parse_json_response(text: str) -> Any:
        """Try to extract and parse JSON from an LLM response.

        Handles ```json fenced blocks and bare JSON.
        """
        # Try ```json ... ``` first
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        # Try to find first { or [ and last } or ]
        start = -1
        for i, ch in enumerate(text):
            if ch in "{[":
                start = i
                break
        if start >= 0:
            end_char = "}" if text[start] == "{" else "]"
            end = text.rfind(end_char)
            if end > start:
                return json.loads(text[start : end + 1])
        return json.loads(text)

    async def _commit_to_project_repo(self, ctx: Context, artifact: Artifact) -> None:
        """Commit the agent's output to the project's git repository.

        If GitPython is not installed or the project repo can't be opened,
        this is a silent no-op — agents should never fail just because we
        couldn't snapshot.
        """
        try:
            from app.foundation.git_repo import open_or_create

            projects_root = ctx.metadata.get("projects_root") if ctx.metadata else None
            project_id = ctx.metadata.get("project_id") if ctx.metadata else None
            if not projects_root or not project_id:
                return  # nothing to commit

            # Materialize the artifact to disk before committing.
            files_to_write: list[tuple[str, str]] = []

            files_meta = artifact.metadata.get("files") if artifact.metadata else None
            if isinstance(files_meta, list):
                for entry in files_meta:
                    if isinstance(entry, dict) and "path" in entry and "content" in entry:
                        files_to_write.append((entry["path"], entry["content"]))
            elif artifact.metadata and isinstance(artifact.metadata.get("path"), str):
                files_to_write.append((artifact.metadata["path"], str(artifact.content)))

            def _do_commit() -> str | None:
                repo = open_or_create(projects_root, project_id)
                if files_to_write:
                    written_paths = []
                    for rel_path, content in files_to_write:
                        target = repo.path / rel_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(content, encoding="utf-8")
                        written_paths.append(rel_path)
                    return repo.commit(
                        message=f"[{self.role.value}] {artifact.name[:60]}",
                        paths=written_paths,
                    )
                return None  # nothing material to commit

            sha = await asyncio.to_thread(_do_commit)
            if sha:
                logger.debug(
                    "agent_git_committed",
                    sha=sha[:7],
                    file_count=len(files_to_write),
                )
        except Exception as exc:  # noqa: BLE001 — non-fatal
            logger.debug("agent_git_commit_skipped", error=str(exc))

    # --- Experience integration -----------------------------------------

    async def query_experience(
        self,
        error_message: str,
        error_type: str = "",
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Search the experience store for similar past errors.

        Returns a list of hint dicts: ``{content, error_type, solution}``.
        Empty list if nothing matches or the store is unavailable.
        """
        try:
            from app.foundation.experience import experience_store

            matches = experience_store.search_similar(
                error_message=error_message,
                context={"agent_role": self.role.value},
                top_k=top_k,
            )
            return [
                {
                    "content": m.final_solution or m.error_message,
                    "error_type": m.error_type,
                    "solution": m.final_solution,
                }
                for m in matches
            ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("agent_query_experience_failed", error=str(exc))
            return []

    async def record_experience(
        self,
        error_message: str,
        error_type: str,
        solution: str,
        success: bool = True,
    ) -> str | None:
        """Persist a new experience to the global store.

        Called by subclasses (or by the orchestrator) when an error has
        been successfully resolved so the next session can learn from it.
        """
        try:
            from app.foundation.experience import experience_store

            return experience_store.add_experience(
                error_message=error_message,
                error_type=error_type,
                context={"agent_role": self.role.value},
                final_solution=solution,
                success=success,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("agent_record_experience_failed", error=str(exc))
            return None

    # --- Default implementations for subclasses to override ---

    def _default_description(self) -> str:
        """Default description for the Agent."""
        return {
            AgentRole.REQUIREMENTS: "Analyze user requirement and produce a PRD document",
            AgentRole.DESIGN: "Produce system design, API contracts, and architecture decisions",
            AgentRole.FRONTEND: "Generate React/Tailwind frontend code for the application",
            AgentRole.BACKEND: "Generate FastAPI backend code and API definitions",
            AgentRole.TESTING: "Generate unit tests and E2E tests",
            AgentRole.REVIEW: "Review all generated code, fix issues, ensure quality",
            AgentRole.DEPLOYMENT: "Build Docker config and start the application",
        }.get(self.role, "Generic agent")

    def _default_plan_summary(self, ctx: Context) -> str:
        """Default plan summary."""
        return f"Execute {self.role.value} tasks based on requirements"

    def _default_plan_steps(self, ctx: Context) -> list[PlanStep]:
        """Default plan steps - subclasses should override."""
        return [
            PlanStep(
                description=f"Analyze requirement for {self.role.value}",
                tool="llm_chat",
                parameters={"prompt": ctx.user_requirement},
            ),
            PlanStep(
                description=f"Generate output for {self.role.value}",
                tool="file_write",
                parameters={"path": f"output/{self.role.value}.txt"},
            ),
        ]
