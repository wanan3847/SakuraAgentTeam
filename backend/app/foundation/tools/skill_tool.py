"""Skill tool — lets the LLM invoke skills via function calling.

Inspired by Claude Code's SkillTool: the LLM can invoke a registered skill
by name with arguments. The skill's output is returned as the tool result.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.logging import get_logger
from app.foundation.tools.base import (
    PermissionResult,
    Tool,
    ToolInput,
    ToolResult,
)

logger = get_logger(__name__)


class SkillInvokeInput(ToolInput):
    """Input for SkillTool."""

    skill_name: str = Field(
        ...,
        description="Name of the skill to invoke (use the `list_skills` tool to see available skills).",
    )
    input_text: str = Field(
        "",
        description="Optional input text to pass to the skill.",
    )


class SkillTool(Tool[SkillInvokeInput]):
    """Invoke a registered skill by name.

    Skills are reusable prompt templates / workflows registered in the
    skill_registry. This tool lets the LLM invoke them via function calling,
    so the model can leverage domain-specific expertise on demand.
    """

    name = "skill_invoke"
    description = (
        "Invoke a registered skill by name. Skills provide domain-specific "
        "expertise (e.g. 'tdd', 'diagnose', 'prototype'). Use the `list_skills` "
        "tool first to see what's available."
    )
    input_schema = SkillInvokeInput
    aliases = ["skill"]

    def is_readonly(self, input_data: SkillInvokeInput) -> bool:
        return True  # Skills are read-only by default (they produce text)

    def check_permissions(
        self, input_data: SkillInvokeInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: SkillInvokeInput, context: dict[str, Any]) -> ToolResult:
        """Invoke the skill."""
        try:
            from app.foundation.skills import skill_registry

            skills = skill_registry.list_skills()
            skill_names = [s["name"] for s in skills]

            if input_data.skill_name not in skill_names:
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        f"Unknown skill: {input_data.skill_name}. "
                        f"Available skills: {skill_names[:20]}"
                    ),
                )

            # Get the skill and invoke it
            skill = skill_registry.get(input_data.skill_name)
            if skill is None:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Skill '{input_data.skill_name}' found in registry but not retrievable.",
                )

            logger.info(
                "skill_tool_invoke",
                skill=input_data.skill_name,
                input_len=len(input_data.input_text),
            )

            # Skills may be sync or async; handle both
            import asyncio
            import inspect

            result: Any
            if inspect.iscoroutinefunction(skill.execute):
                result = await skill.execute(input_data.input_text, context=context)
            else:
                result = await asyncio.to_thread(skill.execute, input_data.input_text, context=context)

            # Normalize result to string
            if isinstance(result, str):
                output = result
            elif isinstance(result, dict):
                import json
                output = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                output = str(result)

            logger.info(
                "skill_tool_complete",
                skill=input_data.skill_name,
                output_len=len(output),
            )

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "skill_name": input_data.skill_name,
                    "output_length": len(output),
                },
            )

        except Exception as e:
            logger.error(
                "skill_tool_error",
                skill=input_data.skill_name,
                error=str(e),
            )
            return ToolResult(
                success=False,
                output="",
                error=f"Skill '{input_data.skill_name}' failed: {e}",
            )


class ListSkillsInput(ToolInput):
    """Input for ListSkillsTool."""

    pattern: str = Field(
        "",
        description="Optional pattern to filter skill names (substring match).",
    )


class ListSkillsTool(Tool[ListSkillsInput]):
    """List all available skills.

    Companion to SkillTool: lets the LLM discover what skills are available
    before invoking one.
    """

    name = "list_skills"
    description = (
        "List all available skills with their names and descriptions. "
        "Use this before invoking a skill to see what's available."
    )
    input_schema = ListSkillsInput
    aliases = ["skills"]

    def is_readonly(self, input_data: ListSkillsInput) -> bool:
        return True

    def check_permissions(
        self, input_data: ListSkillsInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: ListSkillsInput, context: dict[str, Any]) -> ToolResult:
        try:
            from app.foundation.skills import skill_registry

            skills = skill_registry.list_skills()
            if input_data.pattern:
                skills = [s for s in skills if input_data.pattern.lower() in s["name"].lower()]

            if not skills:
                return ToolResult(
                    success=True,
                    output="No skills available. Load skills with /reload or check the skills/ directory.",
                    metadata={"skill_count": 0},
                )

            lines = [f"Available skills ({len(skills)}):"]
            for s in skills:
                name = s.get("name", "?")
                desc = s.get("description", "")[:80]
                lines.append(f"  - {name}: {desc}")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"skill_count": len(skills)},
            )

        except Exception as e:
            logger.error("list_skills_error", error=str(e))
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to list skills: {e}",
            )
