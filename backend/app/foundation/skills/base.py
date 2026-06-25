"""Skill 抽象基类与注册中心。

本模块定义 Skill 系统的核心抽象，灵感来自 Claude Code 的 Skill 机制。
Skill 是一种可被 Agent 调用的能力单元，比 Tool 更高层、更面向任务：
- Tool 偏底层原子操作（读文件、跑命令）
- Skill 偏高层任务编排（生成全栈代码、解释代码、跑测试）

所有 Skill 子类需声明 name / description / tags 类属性，并实现 run 异步方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SkillContext:
    """Skill 执行上下文，承载会话与项目维度的信息。"""

    session_id: str
    project_id: str
    workdir: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Skill 执行结果。"""

    success: bool
    output: str
    data: dict[str, Any] | None = None
    error: str | None = None


class Skill(ABC):
    """Skill 抽象基类。

    子类需覆盖 name / description / tags 类属性，并实现 run 方法。
    """

    name: str = ""
    description: str = ""
    tags: list[str] = []

    @abstractmethod
    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        """执行 Skill。

        Args:
            args: 调用参数（由调用方传入的 dict）
            ctx: 执行上下文

        Returns:
            Skill 执行结果
        """
        ...


class SkillRegistry:
    """Skill 注册中心，负责注册、查找与调用。"""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """注册一个 Skill 实例。"""
        self._skills[skill.name] = skill
        logger.debug("skill_registered", name=skill.name)

    def get(self, name: str) -> Skill | None:
        """按名查找 Skill。"""
        return self._skills.get(name)

    def list_skills(self) -> list[dict]:
        """列出所有已注册 Skill 的元信息。"""
        return [
            {"name": s.name, "description": s.description, "tags": list(s.tags)}
            for s in self._skills.values()
        ]

    async def call(self, name: str, args: dict, ctx: SkillContext) -> SkillResult:
        """按名调用 Skill。

        若 Skill 不存在或执行抛异常，返回 success=False 的 SkillResult。
        """
        skill = self._skills.get(name)
        if skill is None:
            return SkillResult(
                success=False,
                output="",
                error=f"Skill not found: {name}",
            )
        try:
            return await skill.run(args, ctx)
        except Exception as e:
            logger.error("skill_call_failed", name=name, error=str(e))
            return SkillResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {e}",
            )


# 全局单例
skill_registry = SkillRegistry()
