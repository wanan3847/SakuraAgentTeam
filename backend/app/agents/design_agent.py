"""Design Agent - produces system design and API contract from PRD.

Reads PRD output from RequirementsAgent and generates:
- Architecture design document (architecture.md)
- API specification (routes, schemas)
- Database schema suggestions
"""

from typing import List

from app.core.logging import get_logger
from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan

logger = get_logger(__name__)


class DesignAgent(Agent):
    """Design Agent - produces architecture and API contract."""

    role = AgentRole.DESIGN
    description = "Produce system architecture, API contract, and database schema"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Analyze PRD, design architecture, API contract, and database schema"

    def _default_plan_steps(self, ctx: Context) -> List[PlanStep]:
        return [
            PlanStep(description="Analyze PRD and extract components", tool="llm_chat"),
            PlanStep(description="Design system architecture", tool="file_write", parameters={"path": "architecture.md"}),
            PlanStep(description="Define API contract (routes and schemas)", tool="file_write", parameters={"path": "api.md"}),
            PlanStep(description="Design database schema", tool="file_write", parameters={"path": "database.md"}),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate architecture, API contract, and database schema."""
        logger.info("design_agent_execute", session_id=ctx.session_id)

        requirement = ctx.user_requirement

        # Get PRD from requirements agent if available
        prd_output = ctx.get_output(AgentRole.REQUIREMENTS.value)
        features = []
        if prd_output and hasattr(prd_output, "metadata"):
            features = prd_output.metadata.get("features", [])

        # Generate architecture document
        architecture_doc = self._generate_architecture(requirement, features)

        # Generate API specification
        api_doc = self._generate_api(features)

        # Generate database schema
        db_doc = self._generate_database(features)

        # Combine into a single artifact
        combined = f"{architecture_doc}\n\n---\n\n{api_doc}\n\n---\n\n{db_doc}"

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="document",
            name="design.md",
            content=combined,
            metadata={
                "features_count": len(features),
                "api_routes": self._extract_api_routes(features),
                "db_tables": self._extract_tables(features),
                "features": [f["title"] for f in features],
                "files": [
                    {"path": "architecture.md", "content": architecture_doc},
                    {"path": "api.md", "content": api_doc},
                    {"path": "database.md", "content": db_doc},
                ],
            },
        )

        logger.info("design_agent_done", session_id=ctx.session_id)
        return artifact

    def _generate_architecture(self, requirement: str, features: List[dict]) -> str:
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

        doc.extend([
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
        ])

        return "\n".join(doc)

    def _generate_api(self, features: List[dict]) -> str:
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
            doc.append(f"| 方法 | 路径 | 描述 |")
            doc.append(f"|------|------|------|")
            doc.append(f"| GET | `/api/v1/{resource}` | 获取列表 |")
            doc.append(f"| POST | `/api/v1/{resource}` | 创建 |")
            doc.append(f"| GET | `/api/v1/{resource}/{{id}}` | 获取详情 |")
            doc.append(f"| PUT | `/api/v1/{resource}/{{id}}` | 更新 |")
            doc.append(f"| DELETE | `/api/v1/{resource}/{{id}}` | 删除 |")
            doc.append("")

        doc.extend([
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
        ])

        return "\n".join(doc)

    def _generate_database(self, features: List[dict]) -> str:
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

        doc.extend([
            "## 索引建议",
            "",
            "- 各表 `id` 为主键索引",
            "- 状态字段 `status` 建立索引用于过滤查询",
            "- 时间字段 `created_at` 建立索引用于排序",
            "",
        ])

        return "\n".join(doc)

    def _extract_api_routes(self, features: List[dict]) -> List[str]:
        """Extract list of API routes from features."""
        routes = []
        for feature in features:
            resource = feature["title"].lower().replace(" ", "_")
            routes.extend([
                f"GET /api/v1/{resource}",
                f"POST /api/v1/{resource}",
                f"GET /api/v1/{resource}/{{id}}",
                f"PUT /api/v1/{resource}/{{id}}",
                f"DELETE /api/v1/{resource}/{{id}}",
            ])
        return routes

    def _extract_tables(self, features: List[dict]) -> List[str]:
        """Extract list of database tables from features."""
        return [f["title"].lower().replace(" ", "_") + "s" for f in features]
