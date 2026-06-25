"""sakura-backend 启动入口 — PyInstaller 专用

Usage:
    python sakura_backend_launcher.py
    或 PyInstaller 打包后:
        ./sakura-backend
"""
import sys
import os

# PyInstaller 解包目录(sys._MEIPASS)已经自动在 sys.path 前面,
# 所以 `from app.api.main import app` 在打包模式下能直接工作。
# 我们只在非打包模式(开发模式)下手动加 backend 目录到 sys.path。
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

from app.api.main import app  # noqa: E402


def main():
    port = int(os.environ.get("SAKURA_PORT", "8000"))
    host = os.environ.get("SAKURA_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
