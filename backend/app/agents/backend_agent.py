"""Backend Agent - generates FastAPI backend code.

Produces:
- main.py entry point with FastAPI app
- CRUD API routes for each feature
- Database models (SQLAlchemy)
- Pydantic schemas
"""

from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan
from app.core.logging import get_logger

logger = get_logger(__name__)


class BackendAgent(Agent):
    """Backend Agent - generates FastAPI backend code."""

    role = AgentRole.BACKEND
    description = "Generate FastAPI backend: API routes, models, schemas"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Generate FastAPI backend with CRUD endpoints and SQLite database"

    def _default_plan_steps(self, ctx: Context) -> list[PlanStep]:
        return [
            PlanStep(description="Create FastAPI main entry point", tool="file_write"),
            PlanStep(description="Create SQLAlchemy models", tool="file_write"),
            PlanStep(description="Create Pydantic schemas", tool="file_write"),
            PlanStep(description="Create API route handlers", tool="file_write"),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate backend code based on PRD/design.

        有 LLM provider 时调用 LLM 生成后端代码；
        无 LLM 或 LLM 调用失败时回退到模板逻辑。
        """
        logger.info("backend_agent_execute", session_id=ctx.session_id)

        features = self._extract_features(ctx)

        # 优先使用 LLM 生成后端代码
        files_map: dict[str, str] | None = None
        if self.llm is not None:
            try:
                files_map = await self._generate_with_llm(features, ctx)
            except Exception as exc:
                logger.warning(
                    "backend_agent_llm_fallback",
                    error=str(exc),
                )
                files_map = None

        # 无 LLM 或 LLM 失败时使用模板
        if files_map is None:
            files_map = {
                "backend/main.py": self._generate_main(features),
                "backend/models.py": self._generate_models(features),
                "backend/schemas.py": self._generate_schemas(features),
                "backend/routes.py": self._generate_routes(features),
                "backend/requirements.txt": self._generate_requirements(),
            }

        # 确保 requirements.txt 存在（固定内容，LLM 不生成）
        if "backend/requirements.txt" not in files_map or not files_map["backend/requirements.txt"].strip():
            files_map["backend/requirements.txt"] = self._generate_requirements()

        # 按固定顺序构造 artifact 内容
        ordered_paths = [
            "backend/main.py",
            "backend/models.py",
            "backend/schemas.py",
            "backend/routes.py",
            "backend/requirements.txt",
        ]
        content_parts = []
        files_list = []
        for name in ordered_paths:
            code = files_map.get(name, "")
            content_parts.append(f"--- {name} ---\n\n{code}\n\n")
            files_list.append({"path": name, "content": code})

        combined = "\n".join(content_parts)

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="code",
            name="backend_code",
            content=combined,
            metadata={
                "files_generated": len(files_list),
                "features": [f["title"] for f in features],
                "routes_count": len(features) * 5,
                "files": files_list,
            },
        )

        logger.info("backend_agent_done", session_id=ctx.session_id)
        return artifact

    async def _generate_with_llm(
        self, features: list[dict], ctx: Context
    ) -> dict[str, str]:
        """使用 LLM 生成后端 4 个核心代码文件。

        返回 {file_path: content}。解析失败或文件不足时抛异常触发回退。
        """
        features_desc = "\n".join(
            f"- {f['title']}: {f.get('description', '')}" for f in features
        )

        # 读取前序 Agent 的 PRD 作为上下文
        prd_content = ""
        req_output = ctx.get_output(AgentRole.REQUIREMENTS.value)
        if req_output and hasattr(req_output, "content"):
            prd_content = req_output.content

        prompt = f"""你是 FastAPI 后端专家。请根据需求和功能列表生成完整的后端代码。

## 用户需求
{ctx.user_requirement}

## 功能列表
{features_desc}

## PRD 文档（节选）
{prd_content[:2000] if prd_content else "无"}

## 输出要求
生成以下 4 个文件，每个文件严格使用如下格式输出：

### FILE: backend/main.py
```python
# 代码内容
```

### FILE: backend/models.py
```python
# 代码内容
```

### FILE: backend/schemas.py
```python
# 代码内容
```

### FILE: backend/routes.py
```python
# 代码内容
```

代码要求：
- backend/main.py: FastAPI 应用入口，配置 CORS 中间件、/health 健康检查端点、根路径端点，
  并 include_router 引入所有功能路由
- backend/models.py: SQLAlchemy 模型，每个功能对应一个模型类，使用 SQLite 数据库
  (SQLALCHEMY_DATABASE_URL = "sqlite:///./sakura.db")，包含 id/title/description/status/created_at/updated_at 字段
- backend/schemas.py: Pydantic schemas，每个功能提供 Base/Create/Update/Response/ListResponse 类
- backend/routes.py: API 路由，每个功能提供完整 CRUD（GET 列表、POST 创建、GET 单个、PUT 更新、DELETE 删除），
  路由前缀使用 /api/v1/<resource>，提供 get_db 依赖
- 代码要能直接 uvicorn main:app 运行
"""
        response = await self.run_agentic_loop(
            prompt=prompt,
            ctx=ctx,
            system_prompt=self.build_system_prompt(ctx),
        )
        files_map = self.parse_files_block(response)

        # 校验必需的 4 个文件是否都生成了
        required = [
            "backend/main.py",
            "backend/models.py",
            "backend/schemas.py",
            "backend/routes.py",
        ]
        missing = [f for f in required if f not in files_map or not files_map[f].strip()]
        if missing:
            raise ValueError(f"LLM 生成的后端文件不完整，缺少: {missing}")

        return files_map

    def _extract_features(self, ctx: Context) -> list[dict]:
        """Extract features from context."""
        design_output = ctx.get_output(AgentRole.DESIGN.value)
        if design_output and hasattr(design_output, "metadata"):
            features_meta = design_output.metadata.get("features")
            if features_meta:
                return [{"title": f, "description": f"Manage {f}"} for f in features_meta]

        req_output = ctx.get_output(AgentRole.REQUIREMENTS.value)
        if req_output and hasattr(req_output, "metadata"):
            return req_output.metadata.get("features", [])

        return [{"title": "items", "description": "Core items management"}]

    def _generate_requirements(self) -> str:
        """Generate requirements.txt."""
        return """fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.6.0
SQLAlchemy>=2.0.0
aiosqlite>=0.19.0
"""

    def _generate_main(self, features: list[dict]) -> str:
        """Generate main.py."""
        imports = [
            "from fastapi import FastAPI",
            "from fastapi.middleware.cors import CORSMiddleware",
        ]
        route_imports = []
        route_includes = []

        for feature in features:
            resource = feature["title"].lower().replace(" ", "_")
            route_imports.append(f"from routes import {resource}_router")
            route_includes.append(f"    app.include_router({resource}_router)")

        imports_str = "\n".join(imports + route_imports)
        includes_str = "\n".join(route_includes)

        return f"""{imports_str}

app = FastAPI(title="Sakura Generated API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {{"status": "healthy"}}

@app.get("/")
def root():
    return {{"message": "Sakura Generated API", "docs": "/docs"}}

{includes_str}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
"""

    def _generate_models(self, features: list[dict]) -> str:
        """Generate SQLAlchemy models."""
        parts = [
            "from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine",
            "from sqlalchemy.orm import sessionmaker, declarative_base",
            "from datetime import datetime",
            "",
            'SQLALCHEMY_DATABASE_URL = "sqlite:///./sakura.db"',
            "",
            'engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})',
            "SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)",
            "Base = declarative_base()",
            "",
        ]

        for feature in features:
            class_name = feature["title"].replace(" ", "")
            table_name = feature["title"].lower().replace(" ", "_") + "s"

            parts.append(f'''class {class_name}(Base):
    __tablename__ = "{table_name}"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
''')

        parts.append("Base.metadata.create_all(bind=engine)")

        return "\n".join(parts)

    def _generate_schemas(self, features: list[dict]) -> str:
        """Generate Pydantic schemas."""
        parts = [
            "from pydantic import BaseModel",
            "from datetime import datetime",
            "from typing import Optional",
            "",
        ]

        for feature in features:
            name = feature["title"].replace(" ", "")

            parts.append(f"""class {name}Base(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "active"

class {name}Create({name}Base):
    pass

class {name}Update(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class {name}({name}Base):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class {name}Response(BaseModel):
    success: bool = True
    data: Optional[{name}] = None
    error: Optional[dict] = None

class {name}ListResponse(BaseModel):
    success: bool = True
    data: list[{name}] = []
    error: Optional[dict] = None
""")

        return "\n".join(parts)

    def _generate_routes(self, features: list[dict]) -> str:
        """Generate API routes."""
        parts = [
            "from fastapi import APIRouter, Depends, HTTPException",
            "from sqlalchemy.orm import Session",
            "from datetime import datetime",
            "from models import Base, SessionLocal,",
        ]

        model_names = [f["title"].replace(" ", "") for f in features]
        parts[-1] += ", ".join(model_names)

        parts.extend(
            [
                "from schemas import (",
            ]
        )
        for name in model_names:
            parts.append(
                f"    {name}Create, {name}Update, {name}Response, {name}ListResponse, {name},"
            )
        parts.append(")")

        parts.extend(
            [
                "",
                "# Dependency",
                "def get_db():",
                "    db = SessionLocal()",
                "    try:",
                "        yield db",
                "    finally:",
                "        db.close()",
                "",
            ]
        )

        for feature in features:
            name = feature["title"].replace(" ", "")
            resource = feature["title"].lower().replace(" ", "_")
            router_name = resource + "_router"

            parts.append(
                f'{router_name} = APIRouter(prefix="/api/v1/{resource}", tags=["{feature["title"]}"])'
            )
            parts.append("")
            parts.append(f'@{router_name}.get("/", response_model={name}ListResponse)')
            parts.append(f"def list_{resource}(db: Session = Depends(get_db)):")
            parts.append(f"    items = db.query({name}).all()")
            parts.append(f"    return {name}ListResponse(data=items)")
            parts.append("")
            parts.append(f'@{router_name}.post("/", response_model={name}Response)')
            parts.append(
                f"def create_{resource}(item: {name}Create, db: Session = Depends(get_db)):"
            )
            parts.append(f"    db_item = {name}(**item.model_dump())")
            parts.append("    db.add(db_item)")
            parts.append("    db.commit()")
            parts.append("    db.refresh(db_item)")
            parts.append(f"    return {name}Response(data=db_item)")
            parts.append("")
            parts.append(f'@{router_name}.get("/{{item_id}}", response_model={name}Response)')
            parts.append(f"def get_{resource}(item_id: int, db: Session = Depends(get_db)):")
            parts.append(f"    item = db.query({name}).filter({name}.id == item_id).first()")
            parts.append("    if not item:")
            parts.append(
                f'        raise HTTPException(status_code=404, detail="{feature["title"]} not found")'
            )
            parts.append(f"    return {name}Response(data=item)")
            parts.append("")
            parts.append(f'@{router_name}.put("/{{item_id}}", response_model={name}Response)')
            parts.append(
                f"def update_{resource}(item_id: int, update: {name}Update, db: Session = Depends(get_db)):"
            )
            parts.append(f"    item = db.query({name}).filter({name}.id == item_id).first()")
            parts.append("    if not item:")
            parts.append(
                f'        raise HTTPException(status_code=404, detail="{feature["title"]} not found")'
            )
            parts.append("    for key, value in update.model_dump(exclude_unset=True).items():")
            parts.append("        setattr(item, key, value)")
            parts.append("    item.updated_at = datetime.utcnow()")
            parts.append("    db.commit()")
            parts.append("    db.refresh(item)")
            parts.append(f"    return {name}Response(data=item)")
            parts.append("")
            parts.append(f'@{router_name}.delete("/{{item_id}}", response_model={name}Response)')
            parts.append(f"def delete_{resource}(item_id: int, db: Session = Depends(get_db)):")
            parts.append(f"    item = db.query({name}).filter({name}.id == item_id).first()")
            parts.append("    if not item:")
            parts.append(
                f'        raise HTTPException(status_code=404, detail="{feature["title"]} not found")'
            )
            parts.append("    db.delete(item)")
            parts.append("    db.commit()")
            parts.append(f"    return {name}Response(data={{ 'id': item_id, 'deleted': True }})")
            parts.append("")

        return "\n".join(parts)
