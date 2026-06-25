"""Skill 系统模块。

提供 Skill 抽象、注册中心、内置 Skill 与外部 Skill 加载器。
import 时自动注册 11 个内置 Skill。
还支持从 SKILL.md 文件加载 Markdown prompt skill。
"""

from app.foundation.skills.base import (
    Skill,
    SkillContext,
    SkillRegistry,
    SkillResult,
    skill_registry,
)
from app.foundation.skills.builtin import (
    ExplainCodeSkill,
    GenerateFullstackSkill,
    RunTestsSkill,
)
from app.foundation.skills.loader import load_external_skills
from app.foundation.skills.markdown_loader import load_markdown_skills, MarkdownSkill

__all__ = [
    "Skill",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    "skill_registry",
    "GenerateFullstackSkill",
    "ExplainCodeSkill",
    "RunTestsSkill",
    "load_external_skills",
    "load_markdown_skills",
    "MarkdownSkill",
]
