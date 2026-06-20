"""Deployment Agent - generates deployment configuration.

Produces:
- Dockerfile
- docker-compose.yml
- README with deployment instructions

M4-I2: Validates generated docker-compose syntax via `docker compose config`
(dry-run, no actual build, no docker daemon required).
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

from app.agents.base import Agent, PlanStep
from app.agents.types import AgentRole, Artifact, Context, Plan
from app.core.logging import get_logger

logger = get_logger(__name__)


class DeploymentAgent(Agent):
    """Deployment Agent - generates Docker config and deployment instructions."""

    role = AgentRole.DEPLOYMENT
    description = "Generate Docker configuration and deployment instructions"

    def _default_plan_summary(self, ctx: Context) -> str:
        return "Generate Dockerfile, docker-compose, and deployment README"

    def _default_plan_steps(self, ctx: Context) -> list[PlanStep]:
        return [
            PlanStep(description="Create Dockerfile for backend", tool="file_write"),
            PlanStep(description="Create docker-compose.yml", tool="file_write"),
            PlanStep(description="Write deployment README", tool="file_write"),
        ]

    async def execute(self, plan: Plan, ctx: Context) -> Artifact:
        """Generate deployment files + verify docker-compose syntax (M4-I2)."""
        logger.info("deployment_agent_execute", session_id=ctx.session_id)

        dockerfile = self._generate_dockerfile()
        compose = self._generate_docker_compose()
        readme = self._generate_readme()
        frontend_docker = self._generate_frontend_dockerfile()

        # M4-I2: Verify docker-compose syntax via `docker compose config` (dry-run)
        build_verified, verify_msg = await self._verify_compose_syntax(
            compose=compose, dockerfile=dockerfile, frontend_docker=frontend_docker
        )

        parts = []
        for name, code in [
            ("Dockerfile.backend", dockerfile),
            ("Dockerfile.frontend", frontend_docker),
            ("docker-compose.yml", compose),
            ("DEPLOYMENT.md", readme),
        ]:
            parts.append(f"--- {name} ---\n\n{code}\n\n")

        combined = "\n".join(parts)

        artifact = Artifact(
            agent_role=self.role.value,
            artifact_type="config",
            name="deployment_config",
            content=combined,
            metadata={
                "files_generated": 4,
                "deploy_method": "docker-compose",
                "build_verified": build_verified,
                "build_verify_msg": verify_msg,
                "files": [
                    {"path": "backend/Dockerfile", "content": dockerfile},
                    {"path": "frontend/Dockerfile", "content": frontend_docker},
                    {"path": "docker-compose.yml", "content": compose},
                    {"path": "DEPLOYMENT.md", "content": readme},
                ],
            },
        )

        logger.info(
            "deployment_agent_done",
            session_id=ctx.session_id,
            build_verified=build_verified,
        )
        return artifact

    async def _verify_compose_syntax(
        self,
        compose: str,
        dockerfile: str,
        frontend_docker: str,
    ) -> tuple[bool | None, str]:
        """Verify docker-compose syntax without actually building.

        Strategy:
        1. If `docker compose` CLI not available → return (None, "docker CLI not available")
        2. Write files to temp dir
        3. Run `docker compose -f docker-compose.yml config` (dry-run parse)
        4. If exit code 0 → (True, "syntax valid")
        5. Otherwise → (False, stderr output)
        """
        docker = shutil.which("docker")
        if not docker:
            return None, "docker CLI not available (skipping build verification)"

        with tempfile.TemporaryDirectory(prefix="sakura-deploy-") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "docker-compose.yml").write_text(compose, encoding="utf-8")
            (tmp_path / "backend").mkdir()
            (tmp_path / "backend" / "Dockerfile").write_text(dockerfile, encoding="utf-8")
            (tmp_path / "frontend").mkdir()
            (tmp_path / "frontend" / "Dockerfile").write_text(frontend_docker, encoding="utf-8")

            try:
                proc = await asyncio.create_subprocess_exec(
                    docker,
                    "compose",
                    "-f",
                    "docker-compose.yml",
                    "config",
                    "--quiet",
                    cwd=str(tmp_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
                if proc.returncode == 0:
                    return True, "docker-compose syntax valid"
                err = (stderr or stdout).decode("utf-8", errors="replace")[:500]
                return False, f"docker compose config failed: {err.strip()}"
            except TimeoutError:
                return False, "docker compose config timeout (>20s)"
            except Exception as e:
                return False, f"verify error: {e}"

    def _generate_dockerfile(self) -> str:
        """Generate backend Dockerfile."""
        return """FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
"""

    def _generate_frontend_dockerfile(self) -> str:
        """Generate frontend Dockerfile (build step + nginx serve)."""
        return """FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""

    def _generate_docker_compose(self) -> str:
        """Generate docker-compose.yml."""
        return """version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=sqlite:///./sakura.db

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
    ports:
      - "8080:80"
    depends_on:
      - backend

volumes:
  sakura-db:
"""

    def _generate_readme(self) -> str:
        """Generate deployment README."""
        return """# Deployment Guide

## Quick Start (docker-compose)

```bash
docker-compose up --build
```

- Backend: http://localhost:8000
- Backend docs: http://localhost:8000/docs
- Frontend: http://localhost:8080

## Development (without Docker)

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Production Deployment Notes

1. **Security**: Replace `allow_origins=['*']` with specific domains
2. **Database**: Replace SQLite with PostgreSQL for production
3. **Environment Variables**: Use `.env` files for secrets
4. **HTTPS**: Use nginx or Traefik with TLS certificates
5. **Logging**: Enable structured logging (JSON) for production

## Project Structure (Generated)

```
/
├── backend/
│   ├── main.py          # FastAPI entry point
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   ├── routes.py        # API route handlers
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx     # React entry
│   │   ├── App.tsx      # Routing
│   │   ├── api.ts       # API client
│   │   ├── pages.tsx    # Page components
│   │   └── index.css    # Tailwind styles
│   └── package.json
└── docker-compose.yml
```
"""
