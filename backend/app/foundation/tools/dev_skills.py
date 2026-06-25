"""Skill tools: 7 个原 agent 降级为 LLM 可调用的 tool.

设计哲学：参考 Claude Code / Hermes / gstack 三家共同做法——一个 agent
内部按需调起专业工具，不再是"管理 agent 的系统"，而是"一个 agent +
一组 skill 工具"。

每个工具都接收结构化输入、产出结构化输出、记录到 session 状态中。
这样 LLM 可以在 agentic loop 中按需调用 1-7 个 skill，而不需要用户感知
"有 7 个 agent"。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
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


def _write_artifact(artifact_dir: Path, name: str, content: str, artifact_type: str) -> dict[str, Any]:
    """Write a single artifact to disk and return its metadata."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    file_path = artifact_dir / name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return {
        "name": name,
        "path": str(file_path),
        "size": len(content),
        "artifact_type": artifact_type,
    }


def _resolve_artifact_dir(context: dict[str, Any]) -> Path:
    """Get the artifacts output directory from tool context."""
    projects_root = context.get("projects_root") or os.getcwd()
    project_id = context.get("project_id") or f"session-{uuid.uuid4().hex[:8]}"
    return Path(projects_root) / project_id / "artifacts"


def _publish_skill_event(context: dict[str, Any], skill: str, status: str, message: str) -> None:
    """Best-effort publish a skill status event to the EventBus."""
    try:
        from app.orchestration.eventbus import EventBus, Event, EventType
        import app.orchestration.eventbus as _eb_mod

        bus: EventBus = _eb_mod.event_bus
        import asyncio

        asyncio.ensure_future(
            bus.publish(
                Event(
                    event_type=EventType.AGENT_LOG.value,
                    session_id=context.get("session_id", ""),
                    payload={
                        "agent_role": skill,
                        "message": message,
                        "level": "info",
                        "skill_status": status,
                    },
                )
            )
        )
    except Exception:
        pass


# ===== 1. Requirements Skill =====

class RequirementsInput(ToolInput):
    """Input for the requirements analysis skill."""

    requirement: str = Field(..., description="用户的原始需求描述")


class RequirementsSkillTool(Tool[RequirementsInput]):
    """分析用户需求，产出结构化 PRD（产品需求文档）。

    这是原来 requirements_agent 的能力，但降级为可被单 agent 调用的工具。
    """

    name = "skill_requirements"
    description = (
        "分析用户需求，产出结构化 PRD（含功能列表、用户故事、验收标准、MVP 范围）。"
        "在产品开发流程的第一步调用。"
    )
    input_schema = RequirementsInput
    aliases = ["requirements", "需求分析"]

    def is_readonly(self, input_data: RequirementsInput) -> bool:
        return True

    def check_permissions(
        self, input_data: RequirementsInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: RequirementsInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.base import Agent
        from app.agents.types import AgentRole, Context

        _publish_skill_event(context, "requirements", "running", "分析需求中…")

        # 复用原 requirements_agent 的方法（不是实例化新 agent）
        from app.agents.requirements_agent import RequirementsAgent
        from app.agents import _build_llm_provider

        agent = RequirementsAgent(llm_provider=_build_llm_provider())
        ctx = Context(
            session_id=context.get("session_id", "req-skill"),
            project_id=context.get("project_id", "req-skill"),
            user_requirement=input_data.requirement,
        )
        try:
            artifact = await agent._generate_with_llm(agent._build_requirements_prompt(input_data.requirement), ctx)
        except Exception as e:
            logger.error("skill_requirements_failed", error=str(e))
            return ToolResult(success=False, output="", error=f"需求分析失败: {e}")

        # 落盘
        art_dir = _resolve_artifact_dir(context)
        meta = _write_artifact(art_dir, "prd.md", artifact, "requirements")

        _publish_skill_event(context, "requirements", "completed", f"PRD 已生成 ({meta['size']} chars)")

        return ToolResult(
            success=True,
            output=f"# PRD 已生成\n\n```\n{artifact}\n```\n\n保存到: {meta['path']}",
            metadata={"artifact": meta},
        )


# ===== 2. Design Skill =====

class DesignInput(ToolInput):
    """Input for the architecture design skill."""

    requirement: str = Field(..., description="用户原始需求")
    prd: str | None = Field(None, description="已生成的 PRD 文本（可选）")


class DesignSkillTool(Tool[DesignInput]):
    """基于 PRD 产出技术架构设计、API 契约、数据模型。"""

    name = "skill_design"
    description = (
        "基于需求产出技术架构设计：模块划分、API 契约、数据模型、技术选型。"
        "在设计阶段调用。"
    )
    input_schema = DesignInput
    aliases = ["design", "架构设计"]

    def is_readonly(self, input_data: DesignInput) -> bool:
        return True

    def check_permissions(
        self, input_data: DesignInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: DesignInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.design_agent import DesignAgent
        from app.agents import _build_llm_provider
        from app.agents.types import Context

        _publish_skill_event(context, "design", "running", "设计中…")

        agent = DesignAgent(llm_provider=_build_llm_provider())
        ctx = Context(
            session_id=context.get("session_id", "design-skill"),
            project_id=context.get("project_id", "design-skill"),
            user_requirement=input_data.requirement,
        )
        try:
            artifact = await agent._generate_with_llm(input_data.requirement, ctx)
        except Exception as e:
            logger.error("skill_design_failed", error=str(e))
            return ToolResult(success=False, output="", error=f"架构设计失败: {e}")

        art_dir = _resolve_artifact_dir(context)
        meta = _write_artifact(art_dir, "design.md", artifact, "design")
        _publish_skill_event(context, "design", "completed", f"架构设计已生成 ({meta['size']} chars)")

        return ToolResult(
            success=True,
            output=f"# 架构设计已生成\n\n```\n{artifact}\n```\n\n保存到: {meta['path']}",
            metadata={"artifact": meta},
        )


# ===== 3. Frontend Skill =====

class FrontendInput(ToolInput):
    """Input for the frontend code generation skill."""

    requirement: str = Field(..., description="用户原始需求")
    design: str | None = Field(None, description="已生成的架构设计（可选）")


class FrontendSkillTool(Tool[FrontendInput]):
    """生成前端代码（React/Vue + TypeScript）。"""

    name = "skill_frontend"
    description = (
        "生成前端代码：React + TypeScript + Tailwind 组件、页面、状态管理。"
        "在前端开发阶段调用。"
    )
    input_schema = FrontendInput
    aliases = ["frontend", "前端开发"]

    def is_readonly(self, input_data: FrontendInput) -> bool:
        return True

    def check_permissions(
        self, input_data: FrontendInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: FrontendInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.frontend_agent import FrontendAgent
        from app.agents import _build_llm_provider
        from app.agents.types import Context

        _publish_skill_event(context, "frontend", "running", "生成前端代码中…")

        agent = FrontendAgent(llm_provider=_build_llm_provider())
        ctx = Context(
            session_id=context.get("session_id", "frontend-skill"),
            project_id=context.get("project_id", "frontend-skill"),
            user_requirement=input_data.requirement,
        )
        prompt = agent._build_frontend_prompt(input_data.requirement, input_data.design)
        try:
            files_map = await agent._generate_with_llm(prompt, ctx)
        except Exception as e:
            logger.error("skill_frontend_failed", error=str(e))
            return ToolResult(success=False, output="", error=f"前端代码生成失败: {e}")

        art_dir = _resolve_artifact_dir(context)
        written = []
        for path, content in files_map.items():
            meta = _write_artifact(art_dir, path, content, "frontend")
            written.append(meta)
        _publish_skill_event(context, "frontend", "completed", f"前端代码已生成 {len(written)} 个文件")

        output = "# 前端代码已生成\n\n" + "\n".join(f"- `{m['path']}` ({m['size']} chars)" for m in written)
        return ToolResult(success=True, output=output, metadata={"artifacts": written})


# ===== 4. Backend Skill =====

class BackendInput(ToolInput):
    """Input for the backend code generation skill."""

    requirement: str = Field(..., description="用户原始需求")
    design: str | None = Field(None, description="已生成的架构设计（可选）")


class BackendSkillTool(Tool[BackendInput]):
    """生成后端代码（FastAPI/Python）。"""

    name = "skill_backend"
    description = (
        "生成后端代码：FastAPI 路由、SQLAlchemy 模型、Pydantic schema。"
        "在后端开发阶段调用。"
    )
    input_schema = BackendInput
    aliases = ["backend", "后端开发"]

    def is_readonly(self, input_data: BackendInput) -> bool:
        return True

    def check_permissions(
        self, input_data: BackendInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: BackendInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.backend_agent import BackendAgent
        from app.agents import _build_llm_provider
        from app.agents.types import Context

        _publish_skill_event(context, "backend", "running", "生成后端代码中…")

        agent = BackendAgent(llm_provider=_build_llm_provider())
        ctx = Context(
            session_id=context.get("session_id", "backend-skill"),
            project_id=context.get("project_id", "backend-skill"),
            user_requirement=input_data.requirement,
        )
        prompt = agent._build_backend_prompt(input_data.requirement, input_data.design)
        try:
            files_map = await agent._generate_with_llm(prompt, ctx)
        except Exception as e:
            logger.error("skill_backend_failed", error=str(e))
            return ToolResult(success=False, output="", error=f"后端代码生成失败: {e}")

        art_dir = _resolve_artifact_dir(context)
        written = []
        for path, content in files_map.items():
            meta = _write_artifact(art_dir, path, content, "backend")
            written.append(meta)
        _publish_skill_event(context, "backend", "completed", f"后端代码已生成 {len(written)} 个文件")

        output = "# 后端代码已生成\n\n" + "\n".join(f"- `{m['path']}` ({m['size']} chars)" for m in written)
        return ToolResult(success=True, output=output, metadata={"artifacts": written})


# ===== 5. Testing Skill =====

class TestingInput(ToolInput):
    """Input for the test generation skill."""

    requirement: str = Field(..., description="用户原始需求")
    code_summary: str | None = Field(None, description="代码摘要（可选）")


class TestingSkillTool(Tool[TestingInput]):
    """生成测试代码（pytest + React Testing Library）。"""

    name = "skill_testing"
    description = (
        "生成测试代码：pytest 后端测试 + React Testing Library 前端测试。"
        "在测试阶段调用。"
    )
    input_schema = TestingInput
    aliases = ["testing", "test", "测试生成"]

    def is_readonly(self, input_data: TestingInput) -> bool:
        return True

    def check_permissions(
        self, input_data: TestingInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: TestingInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.testing_agent import TestingAgent
        from app.agents import _build_llm_provider
        from app.agents.types import Context

        _publish_skill_event(context, "testing", "running", "生成测试中…")

        agent = TestingAgent(llm_provider=_build_llm_provider())
        ctx = Context(
            session_id=context.get("session_id", "testing-skill"),
            project_id=context.get("project_id", "testing-skill"),
            user_requirement=input_data.requirement,
        )
        prompt = agent._build_testing_prompt(input_data.requirement)
        try:
            test_code = await agent._generate_with_llm(prompt, ctx)
        except Exception as e:
            logger.error("skill_testing_failed", error=str(e))
            return ToolResult(success=False, output="", error=f"测试生成失败: {e}")

        art_dir = _resolve_artifact_dir(context)
        meta = _write_artifact(art_dir, "tests/test_api.py", test_code, "test")
        _publish_skill_event(context, "testing", "completed", f"测试代码已生成 ({meta['size']} chars)")

        return ToolResult(
            success=True,
            output=f"# 测试代码已生成\n\n保存到: {meta['path']} ({meta['size']} chars)",
            metadata={"artifact": meta},
        )


# ===== 6. Review Skill =====

class ReviewInput(ToolInput):
    """Input for the code review skill."""

    requirement: str = Field(..., description="用户原始需求")
    code_summary: str = Field(..., description="需要审查的代码摘要")


class ReviewSkillTool(Tool[ReviewInput]):
    """对代码进行质量审查。"""

    name = "skill_review"
    description = (
        "对生成的代码做质量审查：安全漏洞、性能问题、风格规范、潜在 bug。"
        "在审查阶段调用。"
    )
    input_schema = ReviewInput
    aliases = ["review", "代码审查"]

    def is_readonly(self, input_data: ReviewInput) -> bool:
        return True

    def check_permissions(
        self, input_data: ReviewInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: ReviewInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.review_agent import ReviewAgent
        from app.agents import _build_llm_provider
        from app.agents.types import Context

        _publish_skill_event(context, "review", "running", "审查代码中…")

        agent = ReviewAgent(llm_provider=_build_llm_provider())
        ctx = Context(
            session_id=context.get("session_id", "review-skill"),
            project_id=context.get("project_id", "review-skill"),
            user_requirement=input_data.requirement,
        )
        prompt = agent._build_review_prompt(input_data.requirement, input_data.code_summary)
        try:
            review = await agent.run_agentic_loop(prompt=prompt, ctx=ctx, system_prompt=agent.build_system_prompt(ctx))
        except Exception as e:
            logger.error("skill_review_failed", error=str(e))
            return ToolResult(success=False, output="", error=f"代码审查失败: {e}")

        art_dir = _resolve_artifact_dir(context)
        meta = _write_artifact(art_dir, "review.md", review, "review")
        _publish_skill_event(context, "review", "completed", f"审查报告已生成 ({meta['size']} chars)")

        return ToolResult(
            success=True,
            output=f"# 代码审查报告\n\n```\n{review}\n```\n\n保存到: {meta['path']}",
            metadata={"artifact": meta},
        )


# ===== 7. Deployment Skill =====

class DeploymentInput(ToolInput):
    """Input for the deployment skill."""

    requirement: str = Field(..., description="用户原始需求")
    project_type: str = Field("fullstack", description="项目类型 (fullstack | frontend | backend)")


class DeploymentSkillTool(Tool[DeploymentInput]):
    """生成部署配置和 README 文档。"""

    name = "skill_deployment"
    description = (
        "生成部署配置：Dockerfile + docker-compose + README + 启动脚本。"
        "在部署阶段调用。"
    )
    input_schema = DeploymentInput
    aliases = ["deployment", "deploy", "部署配置"]

    def is_readonly(self, input_data: DeploymentInput) -> bool:
        return True

    def check_permissions(
        self, input_data: DeploymentInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: DeploymentInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.deployment_agent import DeploymentAgent
        from app.agents import _build_llm_provider
        from app.agents.types import Context

        _publish_skill_event(context, "deployment", "running", "生成部署配置中…")

        agent = DeploymentAgent(llm_provider=_build_llm_provider())
        ctx = Context(
            session_id=context.get("session_id", "deploy-skill"),
            project_id=context.get("project_id", "deploy-skill"),
            user_requirement=input_data.requirement,
        )
        prompt = agent._build_deployment_prompt(input_data.requirement, input_data.project_type)
        try:
            readme = await agent._generate_with_llm(prompt, ctx)
        except Exception as e:
            logger.error("skill_deployment_failed", error=str(e))
            return ToolResult(success=False, output="", error=f"部署配置生成失败: {e}")

        art_dir = _resolve_artifact_dir(context)
        meta = _write_artifact(art_dir, "README.md", readme, "deployment")
        _publish_skill_event(context, "deployment", "completed", f"README 已生成 ({meta['size']} chars)")

        return ToolResult(
            success=True,
            output=f"# 部署配置已生成\n\n保存到: {meta['path']}\n\n(readme 长度 {meta['size']} chars)",
            metadata={"artifact": meta},
        )


# ===== 全栈流水线工具（一键串起 6 个 skill） =====

class FullstackInput(ToolInput):
    """Input for the fullstack pipeline tool."""

    requirement: str = Field(..., description="用户的完整需求")


class FullstackSkillTool(Tool[FullstackInput]):
    """一键跑完 6 阶段全栈流水线（需求→设计→前后端→测试→部署）。"""

    name = "skill_fullstack"
    description = (
        "一键跑完完整全栈开发流水线：需求分析 → 架构设计 → 前端代码 → 后端代码 → 测试 → 部署配置。"
        "适合用户给出完整需求后一键生成整个项目。"
    )
    input_schema = FullstackInput
    aliases = ["fullstack", "一键全栈", "build_all"]

    def is_readonly(self, input_data: FullstackInput) -> bool:
        return True

    def check_permissions(
        self, input_data: FullstackInput, context: dict[str, Any]
    ) -> PermissionResult:
        return PermissionResult.ALLOW

    async def call(self, input_data: FullstackInput, context: dict[str, Any]) -> ToolResult:
        from app.agents.requirements_agent import RequirementsAgent
        from app.agents.design_agent import DesignAgent
        from app.agents.frontend_agent import FrontendAgent
        from app.agents.backend_agent import BackendAgent
        from app.agents.testing_agent import TestingAgent
        from app.agents.deployment_agent import DeploymentAgent
        from app.agents import _build_llm_provider
        from app.agents.types import Context

        llm = _build_llm_provider()
        ctx = Context(
            session_id=context.get("session_id", "fullstack"),
            project_id=context.get("project_id", f"fs-{uuid.uuid4().hex[:8]}"),
            user_requirement=input_data.requirement,
        )
        art_dir = _resolve_artifact_dir(context)

        # 共享上下文，stage 间传数据
        stage_outputs: dict[str, str] = {"requirement": input_data.requirement}
        stage_meta: list[dict] = []

        async def _run_stage(skill_name: str, agent_instance, prompt: str, file_name: str, art_type: str) -> str:
            _publish_skill_event(context, skill_name, "running", f"{skill_name} 阶段开始…")
            try:
                content = await agent_instance._generate_with_llm(prompt, ctx)
            except Exception as e:
                logger.error(f"fullstack_{skill_name}_failed", error=str(e))
                raise
            meta = _write_artifact(art_dir, file_name, content, art_type)
            stage_meta.append({"stage": skill_name, "artifact": meta})
            _publish_skill_event(context, skill_name, "completed", f"{skill_name} 阶段完成 ({meta['size']} chars)")
            return content

        try:
            # 1. 需求
            req_agent = RequirementsAgent(llm_provider=llm)
            prd = await _run_stage("requirements", req_agent, req_agent._build_requirements_prompt(input_data.requirement), "prd.md", "requirements")
            stage_outputs["prd"] = prd

            # 2. 设计
            design_agent = DesignAgent(llm_provider=llm)
            design = await _run_stage("design", design_agent, design_agent._build_design_prompt(input_data.requirement, prd), "design.md", "design")
            stage_outputs["design"] = design

            # 3. 前端
            frontend_agent = FrontendAgent(llm_provider=llm)
            frontend_prompt = frontend_agent._build_frontend_prompt(input_data.requirement, design)
            frontend_files = await frontend_agent._generate_with_llm(frontend_prompt, ctx)
            for path, content in frontend_files.items():
                meta = _write_artifact(art_dir, path, content, "frontend")
                stage_meta.append({"stage": "frontend", "artifact": meta})
            _publish_skill_event(context, "frontend", "completed", f"前端 {len(frontend_files)} 个文件")
            stage_outputs["frontend_files"] = json.dumps(frontend_files, ensure_ascii=False)

            # 4. 后端
            backend_agent = BackendAgent(llm_provider=llm)
            backend_prompt = backend_agent._build_backend_prompt(input_data.requirement, design)
            backend_files = await backend_agent._generate_with_llm(backend_prompt, ctx)
            for path, content in backend_files.items():
                meta = _write_artifact(art_dir, path, content, "backend")
                stage_meta.append({"stage": "backend", "artifact": meta})
            _publish_skill_event(context, "backend", "completed", f"后端 {len(backend_files)} 个文件")
            stage_outputs["backend_files"] = json.dumps(backend_files, ensure_ascii=False)

            # 5. 测试
            testing_agent = TestingAgent(llm_provider=llm)
            testing_prompt = testing_agent._build_testing_prompt(input_data.requirement)
            test_code = await _run_stage("testing", testing_agent, testing_prompt, "tests/test_api.py", "test")
            stage_outputs["test_code"] = test_code

            # 6. 部署
            deployment_agent = DeploymentAgent(llm_provider=llm)
            deployment_prompt = deployment_agent._build_deployment_prompt(input_data.requirement, "fullstack")
            readme = await _run_stage("deployment", deployment_agent, deployment_prompt, "README.md", "deployment")
            stage_outputs["readme"] = readme

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"流水线中断: {e}",
                metadata={"stages": stage_meta},
            )

        summary = "# 🌸 全栈项目已生成\n\n"
        summary += f"完成 {len(stage_meta)} 个产出物，保存到 `{art_dir}`：\n\n"
        for s in stage_meta:
            summary += f"- **{s['stage']}** → `{s['artifact']['name']}` ({s['artifact']['size']} chars)\n"

        return ToolResult(
            success=True,
            output=summary,
            metadata={
                "stages": stage_meta,
                "artifact_dir": str(art_dir),
                "total_files": len(stage_meta),
            },
        )
