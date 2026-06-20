"""CLI 配置文件管理 — ~/.sakura/config.toml

默认配置：
  api_url = "http://localhost:8000"
  default_workflow = None  # 让后端自动选
  output_format = "table"  # table | json
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".sakura"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_API_URL = "http://localhost:8000"
ENV_API_URL = "SAKURA_API_URL"
ENV_API_TOKEN = "SAKURA_API_TOKEN"


@dataclass
class Config:
    api_url: str = DEFAULT_API_URL
    api_token: str = ""
    default_workflow: str = ""  # 空 = 让后端自动选
    output_format: str = "table"  # table | json

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v != "" or k in ("api_url",)}

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("wb") as f:
            data = self.to_dict()
            # 简单 toml 序列化（避免引 tomli_w）
            lines = []
            for k, v in data.items():
                if isinstance(v, str):
                    lines.append(f'{k} = "{v}"\n')
                else:
                    lines.append(f"{k} = {v}\n")
            f.write("".join(lines).encode())

    @classmethod
    def load(cls) -> Config:
        cfg = cls()
        # 优先级：环境变量 > 配置文件 > 默认值
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("rb") as f:
                    data = tomllib.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except Exception as e:
                print(f"警告：配置文件解析失败 {CONFIG_FILE}: {e}", file=sys.stderr)
        # 环境变量覆盖
        env_url = os.environ.get(ENV_API_URL)
        if env_url:
            cfg.api_url = env_url
        env_token = os.environ.get(ENV_API_TOKEN)
        if env_token:
            cfg.api_token = env_token
        return cfg


def get_config() -> Config:
    return Config.load()
