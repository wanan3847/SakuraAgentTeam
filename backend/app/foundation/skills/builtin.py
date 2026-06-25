"""内置 Skill 集合。

包含 3 个内置 Skill：
- generate_fullstack: 调 LLM 生成全栈代码（backend/frontend/tests）
- explain_code: 调 LLM 解释指定文件代码
- run_tests: 在指定目录执行测试命令

import 时自动注册到 skill_registry。
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from app.core.logging import get_logger
from app.foundation.llm import LLMProviderFactory
from app.foundation.llm.base import LLMProvider, Message, MessageRole
from app.foundation.skills.base import (
    Skill,
    SkillContext,
    SkillResult,
    skill_registry,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM provider 辅助
# ---------------------------------------------------------------------------


def _get_llm_provider() -> LLMProvider | None:
    """从环境变量构建 LLM provider，未配置返回 None。

    读取 OPENAI_API_KEY / OPENAI_API_BASE / DEFAULT_LLM_MODEL，
    用 LLMProviderFactory.create() 创建 openai provider。
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    if "openai" not in LLMProviderFactory.list_providers():
        return None

    api_base = os.environ.get("OPENAI_API_BASE")
    model = os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o")
    # 去掉 litellm 风格的 provider 前缀（如 openai/gpt-4o → gpt-4o）
    if "/" in model:
        model = model.split("/", 1)[1]

    try:
        return LLMProviderFactory.create(
            provider="openai",
            model=model,
            api_key=api_key,
            base_url=api_base,
        )
    except Exception as e:
        logger.warning("llm_provider_create_failed", error=str(e))
        return None


# ---------------------------------------------------------------------------
# 文件块解析（从 LLM 响应里抽 ### FILE: path / ```code``` 块）
# ---------------------------------------------------------------------------

_FILE_BLOCK_PATTERN = r"### FILE:\s*([^\n]+)\s*```[a-zA-Z]*\n(.*?)```"


def _parse_files_block(text: str) -> dict[str, str]:
    """从 LLM 响应里抽 ### FILE: path / ```code``` 块。"""
    files: dict[str, str] = {}
    for m in re.finditer(_FILE_BLOCK_PATTERN, text, re.DOTALL):
        path = m.group(1).strip()
        content = m.group(2).rstrip()
        files[path] = content
    return files


def _strip_code_fences(text: str) -> str:
    """移除 LLM 输出首尾的 ```...``` 围栏。"""
    text = re.sub(r"^```[a-zA-Z]*\n", "", text, count=1)
    text = re.sub(r"\n```\s*$", "", text, count=1)
    return text


async def _achat(
    provider: LLMProvider, system: str, user: str, max_tokens: int = 2000
) -> str:
    """调一次 LLM，返回文本内容。"""
    messages = [
        Message(role=MessageRole.SYSTEM, content=system),
        Message(role=MessageRole.USER, content=user),
    ]
    resp = await provider.achat(messages, max_tokens=max_tokens)
    return resp.content or ""


# ---------------------------------------------------------------------------
# 内置 Skill 1: generate_fullstack
# ---------------------------------------------------------------------------


class GenerateFullstackSkill(Skill):
    """全栈代码生成 Skill：3 次 LLM 调用生成 backend/frontend/tests。"""

    name = "generate_fullstack"
    description = "调用 LLM 生成全栈代码（FastAPI 后端 + React 前端 + pytest 测试）"
    tags = ["codegen", "fullstack", "llm"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        requirement = str(args.get("requirement", "")).strip()
        if not requirement:
            return SkillResult(
                success=False, output="", error="requirement is required"
            )
        output_dir = args.get("output_dir") or os.path.join(
            "/tmp", f"sakura_fullstack_{os.getpid()}"
        )

        provider = _get_llm_provider()
        if provider is None:
            return SkillResult(
                success=False, output="", error="LLM provider not configured"
            )

        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)

        try:
            backend_files = await self._gen_backend(provider, requirement)
            frontend_files = await self._gen_frontend(provider, requirement)
            test_files = await self._gen_tests(provider, requirement)
        except Exception as e:
            logger.error("generate_fullstack_failed", error=str(e))
            return SkillResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {e}",
            )

        all_files: dict[str, str] = {
            **backend_files,
            **frontend_files,
            **test_files,
        }
        written: list[str] = []
        for rel, content in all_files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            written.append(rel)

        # 自动补 backend/requirements.txt（后端跑起来需要）
        if (
            "backend/main.py" in all_files
            and "backend/requirements.txt" not in all_files
        ):
            (root / "backend" / "requirements.txt").write_text(
                "fastapi>=0.110.0\nuvicorn[standard]>=0.27.0\n"
                "pydantic>=2.6.0\nsqlalchemy>=2.0.0\naiosqlite>=0.19.0\n",
                encoding="utf-8",
            )
            written.append("backend/requirements.txt")

        file_list = "\n".join(f"- {f}" for f in written)
        output = f"已在 {output_dir} 生成 {len(written)} 个文件：\n{file_list}"
        return SkillResult(
            success=True,
            output=output,
            data={"output_dir": output_dir, "files": written},
        )

    async def _gen_backend(
        self, provider: LLMProvider, requirement: str
    ) -> dict[str, str]:
        """生成 FastAPI 后端。"""
        system = (
            "你是资深 Python 后端工程师。生成简洁可运行的 FastAPI 后端代码。"
            "严格要求：1) 用 SQLAlchemy + SQLite + Pydantic v2；2) 每资源生成完整 CRUD 5 个端点；"
            "3) 4 个文件 main.py / models.py / schemas.py / routes.py；4) 代码不假注释；5) 不用 TypeScript/JS 风格。"
        )
        user = f"""需求：{requirement}

按以下格式输出，每个 ### FILE: 后面是完整文件内容：

### FILE: backend/main.py
```python
...
```

### FILE: backend/models.py
```python
...
```

### FILE: backend/schemas.py
```python
...
```

### FILE: backend/routes.py
```python
...
```"""
        txt = await _achat(provider, system, user, max_tokens=3500)
        files = _parse_files_block(txt)
        if not files:
            return {"backend/main.py": _strip_code_fences(txt)}
        return files

    async def _gen_frontend(
        self, provider: LLMProvider, requirement: str
    ) -> dict[str, str]:
        """生成 React 前端。"""
        system = (
            "你是资深 React 前端工程师。生成简洁可运行的 React + Vite + TypeScript 单页应用。"
            "严格要求：1) 用 hooks（useState / useEffect）；2) 调后端用 fetch（默认 http://localhost:8000）；"
            "3) 一个主 App.tsx + index.html + package.json + vite.config.ts；4) CSS 用内联 style 或 <style>；5) 代码可读。"
        )
        user = f"""需求：{requirement}

按以下格式输出：

### FILE: frontend/src/App.tsx
```tsx
...
```

### FILE: frontend/index.html
```html
...
```

### FILE: frontend/package.json
```json
...
```

### FILE: frontend/vite.config.ts
```ts
...
```"""
        txt = await _achat(provider, system, user, max_tokens=3500)
        files = _parse_files_block(txt)
        if not files:
            return {"frontend/src/App.tsx": _strip_code_fences(txt)}
        return files

    async def _gen_tests(
        self, provider: LLMProvider, requirement: str
    ) -> dict[str, str]:
        """生成 pytest 测试。"""
        system = (
            "你是 QA 工程师。生成可运行的 pytest 测试。严格：1) 用 pytest + httpx；"
            "2) 测 5 个 CRUD 端点至少 8 个用例；3) 用 TestClient；4) 不用 import 真实后端模块，直接 copy 出被测代码。"
        )
        user = f"""需求：{requirement}

### FILE: tests/test_api.py
```python
...
```"""
        txt = await _achat(provider, system, user, max_tokens=2000)
        files = _parse_files_block(txt)
        if not files:
            return {"tests/test_api.py": _strip_code_fences(txt)}
        return files


# ---------------------------------------------------------------------------
# 内置 Skill 2: explain_code
# ---------------------------------------------------------------------------


class ExplainCodeSkill(Skill):
    """代码解释 Skill：读文件并调 LLM 解释。"""

    name = "explain_code"
    description = "读取指定文件内容并调用 LLM 解释代码逻辑"
    tags = ["code", "explain", "llm"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        file_path = str(args.get("file_path", "")).strip()
        if not file_path:
            return SkillResult(
                success=False, output="", error="file_path is required"
            )

        path = Path(file_path)
        if not path.is_file():
            return SkillResult(
                success=False,
                output="",
                error=f"file not found: {file_path}",
            )

        provider = _get_llm_provider()
        if provider is None:
            return SkillResult(
                success=False, output="", error="LLM provider not configured"
            )

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"read file failed: {type(e).__name__}: {e}",
            )

        system = (
            "你是资深代码审查工程师。请清晰、准确地解释用户给出的代码："
            "1) 整体功能；2) 关键模块/函数；3) 设计要点与潜在问题。用中文回答。"
        )
        user = f"文件：{file_path}\n\n```\n{content}\n```"
        try:
            explanation = await _achat(provider, system, user, max_tokens=2000)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"LLM call failed: {type(e).__name__}: {e}",
            )

        return SkillResult(
            success=True, output=explanation, data={"file_path": file_path}
        )


# ---------------------------------------------------------------------------
# 内置 Skill 3: run_tests
# ---------------------------------------------------------------------------


class RunTestsSkill(Skill):
    """测试执行 Skill：在指定目录运行测试命令。"""

    name = "run_tests"
    description = "在指定目录执行测试命令（默认 30s 超时）"
    tags = ["test", "shell"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        workdir = args.get("workdir") or ctx.workdir
        test_cmd = args.get("test_cmd", "pytest -v")
        timeout = float(args.get("timeout", 30))

        if not workdir:
            return SkillResult(
                success=False, output="", error="workdir is required"
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                test_cmd,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"spawn failed: {type(e).__name__}: {e}",
            )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return SkillResult(
                success=False,
                output=f"timeout after {timeout}s",
                error="timeout",
                data={"return_code": -1, "timed_out": True},
            )

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        output = stdout + ("\n" + stderr if stderr else "")
        return_code = proc.returncode if proc.returncode is not None else -1
        return SkillResult(
            success=return_code == 0,
            output=output,
            data={"return_code": return_code},
            error=None if return_code == 0 else f"exit code {return_code}",
        )


# ---------------------------------------------------------------------------
# 自动注册内置 Skill
# ---------------------------------------------------------------------------

skill_registry.register(GenerateFullstackSkill())
skill_registry.register(ExplainCodeSkill())
skill_registry.register(RunTestsSkill())


# ---------------------------------------------------------------------------
# 内置 Skill 4: diagnose
# ---------------------------------------------------------------------------


class DiagnoseSkill(Skill):
    """Bug 诊断 Skill：用户提供错误信息 + 文件路径，LLM 分析根因并给出修复建议。"""

    name = "diagnose"
    description = "根据错误信息和文件路径，调 LLM 分析根因并给出修复建议"
    tags = ["debug", "diagnose", "llm"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        error = str(args.get("error", "")).strip()
        file_path = str(args.get("file_path", "")).strip()
        if not error:
            return SkillResult(
                success=False, output="", error="error is required"
            )

        provider = _get_llm_provider()
        if provider is None:
            return SkillResult(
                success=False, output="", error="LLM provider not configured"
            )

        # 读文件内容（可选）
        file_content = ""
        if file_path:
            path = Path(file_path)
            if path.is_file():
                try:
                    file_content = path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning("diagnose_read_file_failed", error=str(e))

        system = (
            "你是资深 Bug 诊断工程师。根据用户给出的错误信息和相关文件内容，"
            "分析根因并给出修复建议。输出格式：\n"
            "1) 根因分析\n2) 修复建议（含代码片段）\n3) 验证步骤\n用中文回答。"
        )
        user_parts = [f"错误信息：\n```\n{error}\n```"]
        if file_content:
            user_parts.append(f"相关文件 {file_path}：\n```\n{file_content}\n```")
        user = "\n\n".join(user_parts)

        try:
            analysis = await _achat(provider, system, user, max_tokens=2000)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"LLM call failed: {type(e).__name__}: {e}",
            )

        return SkillResult(
            success=True,
            output=analysis,
            data={"error": error, "file_path": file_path},
        )


# ---------------------------------------------------------------------------
# 内置 Skill 5: tdd
# ---------------------------------------------------------------------------


class TddSkill(Skill):
    """TDD 流程 Skill：先写测试 → 跑测试看红 → 写实现 → 跑测试看绿。"""

    name = "tdd"
    description = "TDD 流程：生成测试 → 生成实现 → 生成重构建议（3 次 LLM 调用）"
    tags = ["tdd", "test", "llm"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        requirement = str(args.get("requirement", "")).strip()
        if not requirement:
            return SkillResult(
                success=False, output="", error="requirement is required"
            )
        workdir = args.get("workdir") or os.path.join(
            "/tmp", f"sakura_tdd_{os.getpid()}"
        )

        provider = _get_llm_provider()
        if provider is None:
            return SkillResult(
                success=False, output="", error="LLM provider not configured"
            )

        root = Path(workdir)
        root.mkdir(parents=True, exist_ok=True)

        try:
            test_code = await self._gen_test(provider, requirement)
            impl_code = await self._gen_impl(provider, requirement, test_code)
            refactor = await self._gen_refactor(
                provider, requirement, test_code, impl_code
            )
        except Exception as e:
            logger.error("tdd_failed", error=str(e))
            return SkillResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {e}",
            )

        # 写文件
        test_path = root / "test_impl.py"
        impl_path = root / "impl.py"
        test_path.write_text(test_code, encoding="utf-8")
        impl_path.write_text(impl_code, encoding="utf-8")

        output = (
            f"TDD 流程完成，文件已写入 {workdir}：\n"
            f"- test_impl.py（测试）\n- impl.py（实现）\n\n"
            f"重构建议：\n{refactor}"
        )
        return SkillResult(
            success=True,
            output=output,
            data={
                "workdir": workdir,
                "test_code": test_code,
                "impl_code": impl_code,
                "refactor": refactor,
            },
        )

    async def _gen_test(self, provider: LLMProvider, requirement: str) -> str:
        """生成测试代码（红阶段）。"""
        system = (
            "你是 TDD 教练。根据需求生成 pytest 测试代码（先写测试，此时实现还不存在）。"
            "要求：1) 测试覆盖主要场景；2) 假设实现模块名为 impl；3) 输出纯代码，无解释。"
        )
        user = f"需求：{requirement}\n\n生成 test_impl.py："
        txt = await _achat(provider, system, user, max_tokens=1500)
        return _strip_code_fences(txt)

    async def _gen_impl(
        self, provider: LLMProvider, requirement: str, test_code: str
    ) -> str:
        """生成实现代码（绿阶段）。"""
        system = (
            "你是 TDD 教练。根据需求和已有测试，生成最简实现让测试通过。"
            "要求：1) 实现模块名为 impl；2) 输出纯代码，无解释。"
        )
        user = (
            f"需求：{requirement}\n\n"
            f"已有测试：\n```python\n{test_code}\n```\n\n"
            f"生成 impl.py："
        )
        txt = await _achat(provider, system, user, max_tokens=1500)
        return _strip_code_fences(txt)

    async def _gen_refactor(
        self,
        provider: LLMProvider,
        requirement: str,
        test_code: str,
        impl_code: str,
    ) -> str:
        """生成重构建议。"""
        system = "你是 TDD 教练。给出重构建议，保持测试通过。用中文回答。"
        user = (
            f"需求：{requirement}\n\n"
            f"测试：\n```python\n{test_code}\n```\n\n"
            f"实现：\n```python\n{impl_code}\n```\n\n"
            f"重构建议："
        )
        return await _achat(provider, system, user, max_tokens=1000)


# ---------------------------------------------------------------------------
# 内置 Skill 6: web_dev
# ---------------------------------------------------------------------------


class WebDevSkill(Skill):
    """Web 开发 Skill：生成生产级 HTML/CSS/JS。"""

    name = "web_dev"
    description = "根据需求生成生产级 Web 界面（index.html + style.css + script.js）"
    tags = ["web", "frontend", "llm"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        requirement = str(args.get("requirement", "")).strip()
        if not requirement:
            return SkillResult(
                success=False, output="", error="requirement is required"
            )
        output_dir = args.get("output_dir") or os.path.join(
            "/tmp", f"sakura_web_{os.getpid()}"
        )

        provider = _get_llm_provider()
        if provider is None:
            return SkillResult(
                success=False, output="", error="LLM provider not configured"
            )

        system = (
            "你是资深前端工程师。生成生产级 Web 界面，要求："
            "1) 现代化设计，响应式；2) 干净的 HTML/CSS/JS 分离；3) 不依赖外部框架；"
            "4) 代码可读，注释适度。"
        )
        user = f"""需求：{requirement}

按以下格式输出 3 个文件：

### FILE: index.html
```html
...
```

### FILE: style.css
```css
...
```

### FILE: script.js
```javascript
...
```"""
        try:
            txt = await _achat(provider, system, user, max_tokens=3000)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"LLM call failed: {type(e).__name__}: {e}",
            )

        files = _parse_files_block(txt)
        if not files:
            return SkillResult(
                success=False,
                output="",
                error="LLM 未返回有效的 ### FILE: 块",
            )

        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            written.append(rel)

        file_list = "\n".join(f"- {f}" for f in written)
        output = f"已在 {output_dir} 生成 {len(written)} 个文件：\n{file_list}"
        return SkillResult(
            success=True,
            output=output,
            data={"output_dir": output_dir, "files": written},
        )


# ---------------------------------------------------------------------------
# 内置 Skill 7: web_scraper
# ---------------------------------------------------------------------------


class WebScraperSkill(Skill):
    """网页抓取 Skill：用 httpx 抓取 + BeautifulSoup 解析，返回纯文本。"""

    name = "web_scraper"
    description = "抓取网页内容并解析为纯文本（去掉 script/style/nav）"
    tags = ["web", "scraper"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        url = str(args.get("url", "")).strip()
        if not url:
            return SkillResult(
                success=False, output="", error="url is required"
            )

        # 延迟导入，避免依赖缺失时整个模块不可用
        try:
            import httpx
            from bs4 import BeautifulSoup
        except ImportError as e:
            return SkillResult(
                success=False,
                output="",
                error=f"dependency missing: {e.name}. 请安装 httpx 和 beautifulsoup4",
            )

        try:
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"fetch failed: {type(e).__name__}: {e}",
            )

        try:
            soup = BeautifulSoup(html, "html.parser")
            # 去掉 script / style / nav / header / footer
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            # 压缩多余空行
            lines = [line.strip() for line in text.splitlines()]
            lines = [line for line in lines if line]
            text = "\n".join(lines)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"parse failed: {type(e).__name__}: {e}",
            )

        return SkillResult(
            success=True,
            output=text,
            data={"url": url, "length": len(text)},
        )


# ---------------------------------------------------------------------------
# 内置 Skill 8: prototype
# ---------------------------------------------------------------------------


class PrototypeSkill(Skill):
    """快速原型 Skill：生成可运行的终端 app 或 UI 变体。"""

    name = "prototype"
    description = "快速生成可运行原型（终端 app 或 UI 变体）"
    tags = ["prototype", "llm"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        idea = str(args.get("idea", "")).strip()
        if not idea:
            return SkillResult(
                success=False, output="", error="idea is required"
            )
        proto_type = str(args.get("type", "terminal")).strip().lower()
        if proto_type not in ("terminal", "ui"):
            return SkillResult(
                success=False,
                output="",
                error="type must be 'terminal' or 'ui'",
            )
        output_dir = args.get("output_dir") or os.path.join(
            "/tmp", f"sakura_proto_{os.getpid()}"
        )

        provider = _get_llm_provider()
        if provider is None:
            return SkillResult(
                success=False, output="", error="LLM provider not configured"
            )

        if proto_type == "terminal":
            system = (
                "你是原型工程师。生成一个可运行的 Python 终端 app 原型，"
                "用于验证想法。要求：1) 单文件 main.py；2) 用标准库；"
                "3) 可直接 python main.py 运行；4) 包含基本交互循环。"
            )
            file_name = "main.py"
        else:
            system = (
                "你是原型工程师。生成一个单文件 HTML 原型，包含内联 CSS 和 JS，"
                "用于验证 UI 想法。要求：1) 单文件 index.html；2) 现代化样式；"
                "3) 可直接浏览器打开。"
            )
            file_name = "index.html"

        user = f"想法：{idea}\n\n生成 {file_name}："
        try:
            txt = await _achat(provider, system, user, max_tokens=2000)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"LLM call failed: {type(e).__name__}: {e}",
            )

        code = _strip_code_fences(txt)
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        out_path = root / file_name
        out_path.write_text(code, encoding="utf-8")

        output = f"原型已生成：{out_path}"
        return SkillResult(
            success=True,
            output=output,
            data={
                "output_dir": output_dir,
                "file": file_name,
                "type": proto_type,
            },
        )


# ---------------------------------------------------------------------------
# 内置 Skill 9: pdf
# ---------------------------------------------------------------------------


class PdfSkill(Skill):
    """PDF 处理 Skill：提取文本 / 创建 PDF / 合并。"""

    name = "pdf"
    description = "PDF 处理：提取文本 / 创建 PDF / 合并多个 PDF"
    tags = ["pdf", "document"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        action = str(args.get("action", "")).strip().lower()
        if not action:
            return SkillResult(
                success=False, output="", error="action is required"
            )

        # 延迟导入 pypdf
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError as e:
            return SkillResult(
                success=False,
                output="",
                error=f"dependency missing: {e.name}. 请安装 pypdf",
            )

        if action == "extract":
            return await self._extract(args, PdfReader)
        elif action == "create":
            return await self._create(args)
        elif action == "merge":
            return await self._merge(args, PdfWriter, PdfReader)
        else:
            return SkillResult(
                success=False,
                output="",
                error=f"unknown action: {action}. 支持 extract / create / merge",
            )

    async def _extract(self, args: dict, PdfReader) -> SkillResult:
        """提取 PDF 文本。"""
        file_path = str(args.get("file_path", "")).strip()
        if not file_path:
            return SkillResult(
                success=False, output="", error="file_path is required"
            )
        path = Path(file_path)
        if not path.is_file():
            return SkillResult(
                success=False,
                output="",
                error=f"file not found: {file_path}",
            )
        try:
            reader = PdfReader(str(path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages_text.append(f"--- Page {i + 1} ---\n{text}")
            output = "\n\n".join(pages_text)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"extract failed: {type(e).__name__}: {e}",
            )
        return SkillResult(
            success=True,
            output=output,
            data={"file_path": file_path, "pages": len(reader.pages)},
        )

    async def _create(self, args: dict) -> SkillResult:
        """从文本创建简单 PDF（需要 reportlab，未安装时优雅降级）。"""
        text = str(args.get("text", ""))
        output_path = str(args.get("output_path", "")).strip()
        if not output_path:
            return SkillResult(
                success=False, output="", error="output_path is required"
            )
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError as e:
            return SkillResult(
                success=False,
                output="",
                error=(
                    f"dependency missing: {e.name}. 创建 PDF 需要 reportlab，"
                    "请 pip install reportlab"
                ),
            )
        try:
            c = canvas.Canvas(output_path, pagesize=A4)
            width, height = A4
            y = height - 40
            for line in text.splitlines():
                if y < 40:
                    c.showPage()
                    y = height - 40
                c.drawString(40, y, line)
                y -= 15
            c.save()
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"create failed: {type(e).__name__}: {e}",
            )
        return SkillResult(
            success=True,
            output=f"PDF 已创建：{output_path}",
            data={"output_path": output_path},
        )

    async def _merge(
        self, args: dict, PdfWriter, PdfReader
    ) -> SkillResult:
        """合并多个 PDF。"""
        file_paths = args.get("file_paths", [])
        output_path = str(args.get("output_path", "")).strip()
        if not file_paths or not isinstance(file_paths, list):
            return SkillResult(
                success=False,
                output="",
                error="file_paths (list) is required",
            )
        if not output_path:
            return SkillResult(
                success=False, output="", error="output_path is required"
            )
        try:
            writer = PdfWriter()
            for fp in file_paths:
                path = Path(fp)
                if not path.is_file():
                    return SkillResult(
                        success=False,
                        output="",
                        error=f"file not found: {fp}",
                    )
                reader = PdfReader(str(path))
                for page in reader.pages:
                    writer.add_page(page)
            with open(output_path, "wb") as f:
                writer.write(f)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"merge failed: {type(e).__name__}: {e}",
            )
        return SkillResult(
            success=True,
            output=f"已合并 {len(file_paths)} 个 PDF 到 {output_path}",
            data={"output_path": output_path, "count": len(file_paths)},
        )


# ---------------------------------------------------------------------------
# 内置 Skill 10: to_prd
# ---------------------------------------------------------------------------


class ToPrdSkill(Skill):
    """PRD 生成 Skill：把对话上下文转成结构化 PRD 文档。"""

    name = "to_prd"
    description = "把对话上下文转成结构化 PRD 文档（Markdown）"
    tags = ["prd", "document", "llm"]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        context = str(args.get("context", "")).strip()
        if not context:
            return SkillResult(
                success=False, output="", error="context is required"
            )
        output_path = str(args.get("output_path", "")).strip()

        provider = _get_llm_provider()
        if provider is None:
            return SkillResult(
                success=False, output="", error="LLM provider not configured"
            )

        system = (
            "你是资深产品经理。根据用户提供的对话上下文，生成结构化 PRD 文档（Markdown 格式）。"
            "包含：1) 背景与目标；2) 用户故事；3) 功能需求（按优先级）；"
            "4) 非功能需求；5) 验收标准；6) 里程碑。用中文回答。"
        )
        user = f"对话上下文：\n{context}\n\n生成 PRD："
        try:
            prd = await _achat(provider, system, user, max_tokens=2500)
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=f"LLM call failed: {type(e).__name__}: {e}",
            )

        if output_path:
            try:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(prd, encoding="utf-8")
            except Exception as e:
                return SkillResult(
                    success=False,
                    output="",
                    error=f"write file failed: {type(e).__name__}: {e}",
                )

        return SkillResult(
            success=True,
            output=prd,
            data={"output_path": output_path} if output_path else None,
        )


# ---------------------------------------------------------------------------
# 内置 Skill 11: caveman
# ---------------------------------------------------------------------------


class CavemanSkill(Skill):
    """超压缩通信 Skill：去掉填充词、冠词、客套，保留技术准确性。"""

    name = "caveman"
    description = "超压缩通信模式：去掉填充词、冠词、客套，保留技术准确性"
    tags = ["compress", "communication"]

    # 规则替换用的填充词（LLM 不可用时降级用）
    _FILLER_WORDS = [
        "请", "帮", "帮忙", "一下", "那个", "这个", "就是", "其实",
        "麻烦", "能够", "可以", "可能", "应该", "需要", "我觉得",
        "我认为", "我想", "你看", "你看一下", "帮我看", "帮我",
        "请问", "麻烦了", "谢谢", "感谢",
    ]

    async def run(self, args: dict, ctx: SkillContext) -> SkillResult:
        text = str(args.get("text", "")).strip()
        if not text:
            return SkillResult(
                success=False, output="", error="text is required"
            )

        provider = _get_llm_provider()
        if provider is not None:
            # 有 LLM：调 LLM 压缩
            system = (
                "你是超压缩通信助手。把用户输入压缩到最短，去掉填充词、冠词、客套，"
                "保留技术准确性和核心意图。直接输出压缩结果，无解释。"
            )
            user = f"原文：{text}\n\n压缩："
            try:
                compressed = await _achat(
                    provider, system, user, max_tokens=200
                )
                return SkillResult(
                    success=True,
                    output=compressed.strip(),
                    data={"original": text, "mode": "llm"},
                )
            except Exception as e:
                logger.warning("caveman_llm_failed", error=str(e))

        # 无 LLM 或 LLM 失败：规则替换降级
        compressed = self._rule_compress(text)
        return SkillResult(
            success=True,
            output=compressed,
            data={"original": text, "mode": "rule"},
        )

    def _rule_compress(self, text: str) -> str:
        """规则替换压缩：去掉常见填充词。"""
        result = text
        for word in self._FILLER_WORDS:
            result = result.replace(word, "")
        # 压缩多余空格
        result = re.sub(r"\s+", " ", result).strip()
        return result


# ---------------------------------------------------------------------------
# 注册新增 Skill
# ---------------------------------------------------------------------------

skill_registry.register(DiagnoseSkill())
skill_registry.register(TddSkill())
skill_registry.register(WebDevSkill())
skill_registry.register(WebScraperSkill())
skill_registry.register(PrototypeSkill())
skill_registry.register(PdfSkill())
skill_registry.register(ToPrdSkill())
skill_registry.register(CavemanSkill())
