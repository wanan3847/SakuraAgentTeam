"""User LLM 配置模型 — 用户自己保存的 provider/key/url/model。

借鉴 hermes-agent 的 ProviderProfile 设计：
- 用户可以从内置厂商列表选择，也可以完全自定义
- 每个配置包含 base_url + api_key + 默认 model
- 用户可以保存多个配置，切换使用
- 严格区分"内置厂商"（共享元数据）和"用户配置"（私有 key）

Reuses ``Base`` from :mod:`app.auth.database` so the table is created by
``Base.metadata.create_all`` at startup alongside the other tables.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.auth.database import Base


class CustomProvider(Base):
    """用户的 LLM 配置（私有，每个用户独立）。

    一条记录 = 用户保存的一套 LLM 配置：
    - provider_id: 内置厂商 ID（如 deepseek）或 "custom" 表示完全自定义
    - display_name: 用户给这套配置起的名字（如 "我的 DeepSeek 账号"）
    - base_url: API base URL
    - api_key: 用户的私有 API Key（加密存储）
    - model: 默认使用的模型名
    - models: 可用模型列表（JSON）
    - is_active: 是否启用
    - is_default: 是否为当前默认配置（每个用户只能有一个默认）
    """

    __tablename__ = "custom_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    provider_id = Column(String(50), nullable=False)  # 内置厂商 ID 或 "custom"
    display_name = Column(String(100), nullable=False, default="")  # 用户自定义名称
    base_url = Column(String(500), nullable=False)
    api_key = Column(String(500), default="")  # 用户私有 key
    model = Column(String(200), default="")  # 默认模型
    models = Column(Text, default="[]")  # 可用模型列表 JSON
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 是否为默认配置
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
