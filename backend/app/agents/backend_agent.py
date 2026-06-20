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
        """Generate backend code based on PRD/design."""
        logger.info("backend_agent_execute", session_id=ctx.session_id)

        features = self._extract_features(ctx)

        # Generate backend files
        main_py = self._generate_main(features)
        models_py = self._generate_models(features)
        schemas_py = self._generate_schemas(features)
        routes_py = self._generate_routes(features)
        requirements_txt = self._generate_requirements()

        content_parts = []
        for name, code in [
            ("backend/main.py", main_py),
            ("backend/models.py", models_py),
            ("backend/schemas.py", schemas_py),
            ("backend/routes.py", routes_py),
            ("backend/requirements.txt", requirements_txt),
        ]:
            content_parts.append(f"--- {name} ---\n\n{code}\n\n")

        combined = "\n".join(content_parts)

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="code",
            name="backend_code",
            content=combined,
            metadata={
                "files_generated": 5,
                "features": [f["title"] for f in features],
                "routes_count": len(features) * 5,
                "files": [
                    {"path": "backend/main.py", "content": main_py},
                    {"path": "backend/models.py", "content": models_py},
                    {"path": "backend/schemas.py", "content": schemas_py},
                    {"path": "backend/routes.py", "content": routes_py},
                    {"path": "backend/requirements.txt", "content": requirements_txt},
                ],
            },
        )

        logger.info("backend_agent_done", session_id=ctx.session_id)
        return artifact

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
