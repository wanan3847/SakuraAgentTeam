"""Design Agent - produces system design and API contract from PRD.

Reads PRD output from RequirementsAgent and generates:
- Architecture design document (architecture.md)
- API specification (routes, schemas)
- Database schema suggestions
"""

from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan
from app.core.logging import get_logger

logger = get_logger(__name__)


class DesignAgent(Agent):
    """Design Agent - produces architecture and API contract."""

    role = AgentRole.DESIGN
    description = "Produce system architecture, API contract, and database schema"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Analyze PRD, design architecture, API contract, and database schema"

    def _default_plan_steps(self, ctx: Context) -> list[PlanStep]:
        return [
            PlanStep(description="Analyze PRD and extract components", tool="llm_chat"),
            PlanStep(
                description="Design system architecture",
                tool="file_write",
                parameters={"path": "architecture.md"},
            ),
            PlanStep(
                description="Define API contract (routes and schemas)",
                tool="file_write",
                parameters={"path": "api.md"},
            ),
            PlanStep(
                description="Design database schema",
                tool="file_write",
                parameters={"path": "database.md"},
            ),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate architecture, API contract, and database schema.

        有 LLM provider 时调用 LLM 生成针对项目的设计文档；
        无 LLM 或 LLM 调用失败时回退到模板逻辑。
        """
        logger.info("design_agent_execute", session_id=ctx.session_id)

        requirement = ctx.user_requirement

        # Get PRD from requirements agent if available
        prd_output = ctx.get_output(AgentRole.REQUIREMENTS.value)
        features = []
        if prd_output and hasattr(prd_output, "metadata"):
            features = prd_output.metadata.get("features", [])

        # 优先使用 LLM 生成针对项目的设计文档
        llm_result: dict | None = None
        if self.llm is not None:
            try:
                llm_result = await self._generate_with_llm(requirement, features, ctx)
            except Exception as exc:
                logger.warning("design_agent_llm_fallback", error=str(exc))
                llm_result = None

        if llm_result is not None:
            architecture_doc = llm_result["architecture"]
            api_doc = llm_result["api"]
            db_doc = llm_result["database"]
        else:
            # Generate architecture document
            architecture_doc = self._generate_architecture(requirement, features)

            # Generate API specification
            api_doc = self._generate_api(features)

            # Generate database schema
            db_doc = self._generate_database(features)

        # Combine into a single artifact
        combined = f"{architecture_doc}\n\n---\n\n{api_doc}\n\n---\n\n{db_doc}"

        api_routes = self._extract_api_routes(features)
        db_tables = self._extract_tables(features)

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="document",
            name="design.md",
            content=combined,
            metadata={
                "features_count": len(features),
                "api_routes": api_routes,
                "db_tables": db_tables,
                "features": [f["title"] for f in features],
                "files": [
                    {"path": "architecture.md", "content": architecture_doc},
                    {"path": "api.md", "content": api_doc},
                    {"path": "database.md", "content": db_doc},
                ],
            },
        )

        # 向 frontend 和 backend agent 发送 handoff 消息，
        # 告知 API 契约和数据库表结构，便于后续协作
        handoff_content = (
            f"API 契约摘要:\n"
            f"- 基础路径: /api/v1/\n"
            f"- 路由: {', '.join(api_routes) if api_routes else '无'}\n"
            f"- 数据库表: {', '.join(db_tables) if db_tables else '无'}\n"
            f"- 统一响应格式: {{ success, data, error }}\n"
            f"- 数据库表结构详见 design.md"
        )
        ctx.send_message(
            from_role=self.role.value,
            to_role=AgentRole.FRONTEND.value,
            message_type="handoff",
            content=handoff_content,
            api_routes=api_routes,
            db_tables=db_tables,
        )
        ctx.send_message(
            from_role=self.role.value,
            to_role=AgentRole.BACKEND.value,
            message_type="handoff",
            content=handoff_content,
            api_routes=api_routes,
            db_tables=db_tables,
        )

        logger.info("design_agent_done", session_id=ctx.session_id)
        return artifact

    async def _generate_with_llm(
        self, requirement: str, features: list[dict], ctx: Context
    ) -> dict:
        """使用 LLM 生成针对项目的架构、API 契约、数据库设计。

        返回 {"architecture": str, "api": str, "database": str}。
        解析失败或字段缺失时抛异常触发回退。
        """
        features_desc = "\n".join(
            f"- {f['title']}: {f.get('description', '')}" for f in features
        )
        prd_content = ""
        req_output = ctx.get_output(AgentRole.REQUIREMENTS.value)
        if req_output and hasattr(req_output, "content"):
            prd_content = req_output.content

        prompt = f"""你是资深系统架构师。请根据用户需求和功能列表，生成针对该项目的架构设计文档。

## 用户需求
{requirement}

## 功能列表
{features_desc if features_desc else "无"}

## PRD 文档（节选）
{prd_content[:2000] if prd_content else "无"}

## 输出要求
返回 JSON 对象，格式如下：
```json
{{
  "architecture": "# System Architecture\\n\\n## 1. 总体架构\\n\\n(针对该项目的架构描述)\\n\\n## 2. 核心组件\\n\\n...",
  "api": "# API Contract\\n\\n## API 端点\\n\\n...",
  "database": "# Database Schema\\n\\n## 表结构\\n\\n..."
}}
```

要求：
- architecture: 针对该项目业务特点的架构描述，至少 800 字，包含总体架构、核心组件、技术栈、设计原则
- api: 针对功能的 REST API 端点表（CRUD），统一响应格式 {{ success, data, error }}
- database: 数据库表结构，每个表至少包含 id/title/status/created_at/updated_at 字段，
  对每个字段标注类型、约束、说明
- 只返回 JSON，不要其他文字
"""
        response = await self.run_agentic_loop(
            prompt=prompt,
            ctx=ctx,
            system_prompt=self.build_system_prompt(ctx),
        )
        parsed = self.parse_json_response(response)
        if not isinstance(parsed, dict):
            raise ValueError("LLM 返回的不是 JSON 对象")
        for key in ("architecture", "api", "database"):
            val = parsed.get(key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"LLM 返回的 {key} 字段为空或非字符串")
        return {
            "architecture": parsed["architecture"],
            "api": parsed["api"],
            "database": parsed["database"],
        }

    def _generate_architecture(self, requirement: str, features: list[dict]) -> str:
        """Generate architecture document."""
        doc = [
            "# System Architecture",
            "",
            "## 1. 总体架构",
            "",
            "采用前后端分离的三层架构：",
            "",
            "```",
            "用户界面 (React SPA)",
            "    ↓ HTTPS / JSON",
            "API 网关 (FastAPI)",
            "    ↓",
            "业务逻辑层",
            "    ↓",
            "数据访问层",
            "    ↓",
            "数据库 (SQLite → PostgreSQL)",
            "```",
            "",
            "## 2. 核心组件",
            "",
        ]

        for i, feature in enumerate(features, 1):
            doc.append(f"### 2.{i} {feature['title']} 组件")
            doc.append("")
            doc.append(f"- **前端**: {feature['title']}页面组件")
            doc.append(f"- **后端**: {feature['title']} API 路由 + 服务")
            doc.append(f"- **数据**: {feature['title']} 相关数据表")
            doc.append("")

        doc.extend(
            [
                "## 3. 技术栈决策",
                "",
                "| 层 | 技术选择 | 理由 |",
                "|----|---------|------|",
                "| 前端 | React 18 + TypeScript | 生态成熟、类型安全 |",
                "| 样式 | Tailwind CSS | 快速构建、无需切换文件 |",
                "| 状态 | Zustand | 轻量级、简单易用 |",
                "| 后端 | FastAPI + Python 3.11 | 高性能、自动文档、类型提示 |",
                "| 数据库 | SQLite (MVP) → PostgreSQL | 零配置起步、可平滑升级 |",
                "| 通信 | REST API | 简单、调试方便 |",
                "| 部署 | Docker | 一键运行 |",
                "",
                "## 4. 设计原则",
                "",
                "- **关注点分离**: 前端/后端各自独立，通过 API 解耦",
                "- **单一职责**: 每个组件/模块只做一件事",
                "- **约定优于配置**: 遵循主流框架的默认方式",
                "- **渐进式完善**: 先实现核心功能，再逐步打磨",
                "",
            ]
        )

        return "\n".join(doc)

    def _generate_api(self, features: list[dict]) -> str:
        """Generate API specification."""
        doc = [
            "# API Contract",
            "",
            "## 全局约定",
            "",
            "- **基础路径**: `/api/v1/`",
            "- **数据格式**: JSON (UTF-8)",
            "- **认证**: API Key / JWT Token (按需)",
            "- **响应格式**: 统一 `{ success, data, error }`",
            "",
            "## API 端点",
            "",
        ]

        # Generate CRUD endpoints for each feature
        for i, feature in enumerate(features, 1):
            resource = feature["title"].lower().replace(" ", "_")
            doc.append(f"### {i}. {feature['title']} API")
            doc.append("")
            doc.append("| 方法 | 路径 | 描述 |")
            doc.append("|------|------|------|")
            doc.append(f"| GET | `/api/v1/{resource}` | 获取列表 |")
            doc.append(f"| POST | `/api/v1/{resource}` | 创建 |")
            doc.append(f"| GET | `/api/v1/{resource}/{{id}}` | 获取详情 |")
            doc.append(f"| PUT | `/api/v1/{resource}/{{id}}` | 更新 |")
            doc.append(f"| DELETE | `/api/v1/{resource}/{{id}}` | 删除 |")
            doc.append("")

        doc.extend(
            [
                "## 统一响应格式",
                "",
                "```json",
                "{",
                '  "success": true,',
                '  "data": { ... },',
                '  "error": null',
                "}",
                "```",
                "",
                "## 错误响应",
                "",
                "```json",
                "{",
                '  "success": false,',
                '  "data": null,',
                '  "error": {',
                '    "code": "RESOURCE_NOT_FOUND",',
                '    "message": "Resource not found"',
                "  }",
                "}",
                "```",
                "",
            ]
        )

        return "\n".join(doc)

    def _generate_database(self, features: list[dict]) -> str:
        """Generate database schema."""
        doc = [
            "# Database Schema",
            "",
            "## 表结构",
            "",
        ]

        for i, feature in enumerate(features, 1):
            table = feature["title"].lower().replace(" ", "_") + "s"
            doc.append(f"### 表 {i}: `{table}`")
            doc.append("")
            doc.append("| 字段 | 类型 | 约束 | 描述 |")
            doc.append("|------|------|------|------|")
            doc.append("| `id` | INTEGER | PRIMARY KEY, AUTO_INCREMENT | 主键 |")
            doc.append("| `title` / `name` | VARCHAR(255) | NOT NULL | 名称 |")
            doc.append("| `description` | TEXT | NULLABLE | 描述 |")
            doc.append("| `status` | VARCHAR(50) | DEFAULT 'active' | 状态 |")
            doc.append("| `created_at` | TIMESTAMP | DEFAULT NOW() | 创建时间 |")
            doc.append("| `updated_at` | TIMESTAMP | DEFAULT NOW() | 更新时间 |")
            doc.append("")

        doc.extend(
            [
                "## 索引建议",
                "",
                "- 各表 `id` 为主键索引",
                "- 状态字段 `status` 建立索引用于过滤查询",
                "- 时间字段 `created_at` 建立索引用于排序",
                "",
            ]
        )

        return "\n".join(doc)

    def _extract_api_routes(self, features: list[dict]) -> list[str]:
        """Extract list of API routes from features."""
        routes = []
        for feature in features:
            resource = feature["title"].lower().replace(" ", "_")
            routes.extend(
                [
                    f"GET /api/v1/{resource}",
                    f"POST /api/v1/{resource}",
                    f"GET /api/v1/{resource}/{{id}}",
                    f"PUT /api/v1/{resource}/{{id}}",
                    f"DELETE /api/v1/{resource}/{{id}}",
                ]
            )
        return routes

    def _extract_tables(self, features: list[dict]) -> list[str]:
        """Extract list of database tables from features."""
        return [f["title"].lower().replace(" ", "_") + "s" for f in features]
