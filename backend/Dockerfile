# Backend runtime for SakuraAgentTeam
FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# GitPython 和项目生成流程需要容器内有 git 可执行文件。
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 运行时数据目录（建议通过 volume 挂载到主机）
RUN mkdir -p /app/data
ENV PROJECTS_ROOT=/app/data/projects \
    EXPERIENCE_DB_PATH=/app/data/experience_db \
    DATA_DIR=/app/data \
    LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" \
    || exit 1

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
