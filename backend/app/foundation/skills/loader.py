"""外部 Skill 加载器。

从指定目录加载外部 Skill 文件。每个 .py 文件需定义一个继承 Skill 的类，
并实例化后赋值给模块级变量 `skill`，例如：

    from app.foundation.skills.base import Skill, SkillContext, SkillResult

    class MySkill(Skill):
        name = "my_skill"
        description = "做某件事"
        tags = ["custom"]

        async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
            ...

    skill = MySkill()

加载失败的文件会跳过并打 warning log，不影响其他文件加载。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.core.logging import get_logger
from app.foundation.skills.base import Skill, skill_registry

logger = get_logger(__name__)


def load_external_skills(directory: str = "~/.sakura/skills") -> int:
    """从目录加载外部 Skill。

    Args:
        directory: 外部 skill 目录路径，支持 ~ 展开

    Returns:
        成功加载并注册的 skill 数量
    """
    dir_path = Path(directory).expanduser()
    if not dir_path.is_dir():
        logger.info("external_skills_dir_not_found", directory=str(dir_path))
        return 0

    loaded = 0
    for py_file in sorted(dir_path.glob("*.py")):
        # 跳过 __init__.py / _ 前缀的私有文件
        if py_file.name.startswith("_"):
            continue

        module_name = f"_sakura_external_skill_{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                logger.warning(
                    "external_skill_load_failed",
                    file=str(py_file),
                    reason="invalid spec",
                )
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            logger.warning(
                "external_skill_load_failed",
                file=str(py_file),
                error=f"{type(e).__name__}: {e}",
            )
            continue

        skill_obj = getattr(module, "skill", None)
        if not isinstance(skill_obj, Skill):
            logger.warning(
                "external_skill_invalid",
                file=str(py_file),
                reason="no `skill` variable of type Skill",
            )
            continue

        try:
            skill_registry.register(skill_obj)
            loaded += 1
        except Exception as e:
            logger.warning(
                "external_skill_register_failed",
                file=str(py_file),
                error=f"{type(e).__name__}: {e}",
            )
            continue

    logger.info("external_skills_loaded", count=loaded, directory=str(dir_path))
    return loaded
