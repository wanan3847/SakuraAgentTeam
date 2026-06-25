"""Markdown SKILL.md 加载器。

扫描目录下的 SKILL.md 文件，解析 YAML frontmatter，
把每个 SKILL.md 注册成一个 MarkdownSkill。

支持 Claude Code / TRAE / Open Agent Skill 规范的 SKILL.md 格式：
    ---
    name: skill-name
    description: ...
    triggers:
      - keyword1
      - keyword2
    ---
    # Skill body (prompt content)
    ...
"""

import os
import re
from pathlib import Path

from app.core.logging import get_logger
from app.foundation.skills.base import Skill, SkillContext, SkillResult, skill_registry

logger = get_logger(__name__)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (metadata, body)。

    简单实现，不依赖 PyYAML（避免引入新依赖）。
    只解析顶层 key: value 和 list。
    """
    metadata: dict = {}
    body = content

    # 匹配 --- ... ---
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return metadata, content

    yaml_text = match.group(1)
    body = match.group(2)

    # 简单解析 YAML
    current_key = None
    for line in yaml_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # list item: "- value"
        if stripped.startswith("- ") and current_key:
            val = stripped[2:].strip().strip('"').strip("'")
            if current_key not in metadata:
                metadata[current_key] = []
            if isinstance(metadata[current_key], list):
                metadata[current_key].append(val)
            continue

        # key: value
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            # 去掉引号
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            # 多行描述以 > 或 | 开头时，收集后续缩进行
            if val in (">", "|", "|-", ">-"):
                current_key = key
                metadata[key] = ""
                continue
            if val == "":
                current_key = key
                if key not in metadata:
                    metadata[key] = []
                continue
            # 去掉多行描述的折叠标记
            if val.startswith(">"):
                val = val[1:].strip()
            metadata[key] = val
            current_key = key
            continue

        # 多行值的续行（缩进行）
        if current_key and stripped:
            existing = metadata.get(current_key, "")
            if isinstance(existing, str):
                metadata[current_key] = (existing + " " + stripped).strip()

    return metadata, body


class MarkdownSkill(Skill):
    """从 SKILL.md 文件加载的 Skill。

    调用时把 SKILL.md 的 body 作为 system prompt 发给 LLM，
    用户输入作为 user message。
    """

    def __init__(self, name: str, description: str, prompt_body: str, source_path: str, tags: list[str] | None = None):
        self.name = name
        self.description = description or f"SKILL.md skill from {source_path}"
        self.tags = tags or ["markdown", "skill"]
        self._prompt_body = prompt_body
        self._source_path = source_path

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        """调用 LLM 执行 skill。

        args 里可以包含:
        - input / requirement / text: 用户输入（作为 user message）
        - 任何其他 key 都会拼到 user message 里
        """
        # 获取用户输入
        user_input = (
            args.get("input")
            or args.get("requirement")
            or args.get("text")
            or args.get("query")
            or ""
        )

        # 如果有其他 args，拼到输入里
        extra_args = {k: v for k, v in args.items() if k not in ("input", "requirement", "text", "query")}
        if extra_args:
            user_input += f"\n\n附加参数:\n" + "\n".join(f"  {k}: {v}" for k, v in extra_args.items())

        if not user_input:
            # 没有 user input，直接返回 skill 的 prompt body 作为说明
            return SkillResult(
                success=True,
                output=f"Skill: {self.name}\n\n{self._prompt_body[:2000]}",
                data={"source": self._source_path, "prompt_length": len(self._prompt_body)},
            )

        # 调 LLM
        try:
            from app.foundation.llm import LLMProviderFactory
            from app.foundation.llm.base import Message, MessageRole

            provider = _get_llm_provider()
            if not provider:
                return SkillResult(
                    success=False,
                    output=self._prompt_body[:3000],
                    error="LLM provider not configured. Set OPENAI_API_KEY in .env",
                )

            messages = [
                Message(role=MessageRole.SYSTEM, content=self._prompt_body),
                Message(role=MessageRole.USER, content=user_input),
            ]

            # 支持 MeteredLLMProvider
            try:
                from app.foundation.llm.meter import MeteredLLMProvider

                if isinstance(provider, MeteredLLMProvider):
                    resp = await provider.achat(
                        messages,
                        session_id=ctx.session_id,
                        agent_role=f"skill:{self.name}",
                    )
                else:
                    resp = await provider.achat(messages)
            except Exception:
                resp = await provider.achat(messages)

            return SkillResult(
                success=True,
                output=resp.content,
                data={
                    "source": self._source_path,
                    "model": resp.model,
                    "usage": resp.usage,
                },
            )
        except Exception as e:
            logger.warning("markdown_skill_failed", skill=self.name, error=str(e))
            return SkillResult(
                success=False,
                output=self._prompt_body[:2000],
                error=f"Skill execution failed: {e}",
            )


def _get_llm_provider():
    """获取 LLM provider（复用 builtin.py 的逻辑）。"""
    import os

    from app.foundation.llm import LLMProviderFactory

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key or "your-openai-key" in api_key:
        return None

    api_base = os.environ.get("OPENAI_API_BASE") or os.environ.get("DASHSCOPE_API_BASE")
    model = os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o")

    provider_name = os.environ.get("DEFAULT_LLM_PROVIDER", "openai")
    if provider_name == "litellm" or "/" in model:
        provider_name = "litellm"
    elif provider_name not in ("openai", "anthropic", "litellm"):
        provider_name = "openai"

    try:
        # 检查是否已有全局 metered provider
        from app.foundation.llm.meter import get_global_provider

        existing = get_global_provider()
        if existing:
            return existing

        inner = LLMProviderFactory.create(
            provider=provider_name,
            model=model,
            api_key=api_key,
            base_url=api_base,
        )
        from app.foundation.llm.meter import MeteredLLMProvider

        return MeteredLLMProvider(inner)
    except Exception as e:
        logger.warning("llm_provider_build_failed", error=str(e))
        return None


def load_markdown_skills(directory: str = None) -> int:
    """从目录加载所有 SKILL.md 文件，注册到 skill_registry。

    Args:
        directory: skill 目录路径。默认按优先级查找：
            1. 项目根的 skills/ 目录
            2. ~/.sakura/skills/ 目录

    Returns:
        成功加载的 skill 数量
    """
    # 确定搜索目录
    search_dirs: list[Path] = []
    if directory:
        search_dirs.append(Path(directory).expanduser())
    else:
        # 项目根 skills/
        project_skills = Path(__file__).parent.parent.parent.parent.parent / "skills"
        if project_skills.exists():
            search_dirs.append(project_skills)
        # ~/.sakura/skills/
        home_skills = Path.home() / ".sakura" / "skills"
        if home_skills.exists():
            search_dirs.append(home_skills)

    if not search_dirs:
        logger.info("no_skill_directories_found")
        return 0

    loaded = 0
    seen_names: set[str] = set()

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue

        logger.info("scanning_skill_directory", path=str(search_dir))

        # 遍历子目录
        for item in sorted(search_dir.iterdir()):
            if not item.is_dir():
                continue

            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                # 有些 skill 是 symlink，SKILL.md 可能在 symlink 目标里
                try:
                    skill_md = item.resolve() / "SKILL.md"
                    if not skill_md.exists():
                        continue
                except Exception:
                    continue

            try:
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                metadata, body = _parse_frontmatter(content)

                name = metadata.get("name", item.name)
                description = metadata.get("description", "")

                # 跳过已注册的（避免重复）
                if name in seen_names:
                    continue
                # 跳过已注册的内置 skill
                if skill_registry.get(name) is not None:
                    seen_names.add(name)
                    continue

                seen_names.add(name)

                # 提取 triggers 作为 tags
                tags = ["markdown"]
                triggers = metadata.get("triggers", [])
                if isinstance(triggers, list):
                    tags.extend(triggers[:3])  # 最多加 3 个 trigger 作为 tag

                skill = MarkdownSkill(
                    name=name,
                    description=description,
                    prompt_body=body.strip(),
                    source_path=str(skill_md),
                    tags=tags,
                )
                skill_registry.register(skill)
                loaded += 1

            except Exception as e:
                logger.warning("skill_load_failed", path=str(skill_md), error=str(e))
                continue

    logger.info("markdown_skills_loaded", count=loaded, total_seen=len(seen_names))
    return loaded
