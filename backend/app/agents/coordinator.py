"""Unified Coordinator agent — single agent that orchestrates skill tools.

This is the new architecture: ONE agent (not 7). The agent runs an agentic
loop and decides which skill tools to call based on the user's request.
The 7 former sub-agents are now tools, registered in the tool registry.

Why this is better:
- User experience: one conversation, one final answer
- Architecture: clean separation between reasoning (the agent) and skills (tools)
- Matches the pattern used by Claude Code, Hermes, gstack — the industry standard

The agent has access to:
- 7 dev skill tools (requirements, design, frontend, backend, testing, review, deployment)
- 1 fullstack tool (one-click pipeline)
- File ops (read, write, edit)
- Shell, glob, grep
- Sub-agent, skill discovery
"""

from __future__ import annotations

from app.agents.base import Agent
from app.agents.types import AgentRole
from app.foundation.tools import tool_registry


# 确保 skill 工具被注册
def ensure_skills_registered() -> None:
    """Register all dev skill tools on first import."""
    from app.foundation.tools.dev_skills import (
        RequirementsSkillTool,
        DesignSkillTool,
        FrontendSkillTool,
        BackendSkillTool,
        TestingSkillTool,
        ReviewSkillTool,
        DeploymentSkillTool,
        FullstackSkillTool,
    )

    skills = [
        RequirementsSkillTool(),
        DesignSkillTool(),
        FrontendSkillTool(),
        BackendSkillTool(),
        TestingSkillTool(),
        ReviewSkillTool(),
        DeploymentSkillTool(),
        FullstackSkillTool(),
    ]
    for s in skills:
        # 幂等注册
        tool_registry.register(s)


# 模块导入时即注册
ensure_skills_registered()


# Coordinator 专用的 system prompt — 一个 agent 调度所有 skill
COORDINATOR_SYSTEM_PROMPT = """你是 智汇协同🌸 的 Coordinator agent —— 一个为知识工作者服务的多能力 AI 伙伴。

## 你的能力
你拥有 7 个专业 skill 工具，可以按需调用：
- `skill_requirements`: 需求分析（产出 PRD）
- `skill_design`: 架构设计（产出技术方案、API 契约、数据模型）
- `skill_frontend`: 前端代码生成（React + TypeScript + Tailwind）
- `skill_backend`: 后端代码生成（FastAPI + SQLAlchemy）
- `skill_testing`: 测试代码生成（pytest + React Testing Library）
- `skill_review`: 代码审查（安全、性能、规范）
- `skill_deployment`: 部署配置（Dockerfile + docker-compose + README）
- `skill_fullstack`: 一键全栈流水线（6 阶段串起来）

外加基础工具：file_read / file_write / file_edit / glob / grep / shell_run / sub_agent / list_skills / skill_invoke

## 你的工作方式
- 听到用户需求后，先判断需要调哪些 skill
- 对简单任务（如"解释一段代码"），直接用 file_read / grep 即可，不需要调 skill
- 对完整项目（如"做一个图书管理系统"），调 `skill_fullstack` 一键跑通
- 对部分项目（如"先做前端"），单独调 `skill_frontend`
- 调完工具后，把结果用自然语言整理成最终回复

## 你的回复风格
- 像一个有经验的同事，简明扼要
- 涉及到具体技术时给出细节
- 任务完成后给一个清晰的总结
- 中文回复，简短专业
"""


class CoordinatorAgent(Agent):
    """The single unified agent that orchestrates everything."""

    role = AgentRole.REQUIREMENTS  # 复用其中一个 role
    description = "智汇协同 Coordinator —— 调度所有 skill 工具的统一 agent"
    system_prompt = COORDINATOR_SYSTEM_PROMPT

    def __init__(self, llm_provider=None, tools=None):
        super().__init__(llm_provider=llm_provider, tools=tools)

    async def execute(self, plan, ctx):
        """Coordinator 不走 plan→execute 模式，直接跑 agentic loop。"""
        raise NotImplementedError("Coordinator uses run_agentic_loop directly")

    async def run(self, ctx):
        """Coordinator 模式：直接执行用户需求。"""
        from app.foundation.llm.base import Message, MessageRole

        messages = [
            Message(role=MessageRole.SYSTEM, content=self.system_prompt),
            Message(role=MessageRole.USER, content=ctx.user_requirement),
        ]

        result = await self.run_agentic_loop(
            prompt=ctx.user_requirement,
            ctx=ctx,
            system_prompt=self.system_prompt,
        )
        return result


# 全局单例
_coordinator: CoordinatorAgent | None = None


def get_coordinator(llm_provider=None) -> CoordinatorAgent:
    """Get or create the global Coordinator agent."""
    global _coordinator
    if _coordinator is None:
        from app.agents import _build_llm_provider

        _coordinator = CoordinatorAgent(llm_provider=llm_provider or _build_llm_provider())
    return _coordinator
