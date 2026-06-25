"""sakura-backend 启动入口 — PyInstaller 专用

Usage:
    python -m sakura_backend_launcher
    或 PyInstaller 打包后:
        ./sakura-backend
"""
import sys
import os

# 让 uvicorn 能找到 app 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

from app.api.main import app  # noqa: E402


def main():
    port = int(os.environ.get("SAKURA_PORT", "8000"))
    host = os.environ.get("SAKURA_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
