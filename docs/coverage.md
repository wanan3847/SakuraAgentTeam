# 测试覆盖率报告

> 跑测命令：`cd backend && python3 -m pytest tests/ --cov=app --cov-report=term-missing`
>
> 报告日期：2026-06-20

## 总览

| 指标 | 数值 |
|------|------|
| 总代码行 | 2172 |
| 已覆盖 | 1514 |
| **总覆盖率** | **70%** |
| 测试用例 | 26（全部通过） |
| 失败 | 0 |
| 警告 | 0 |

## 各模块明细

### 优秀（≥90%）

| 模块 | 覆盖 | 备注 |
|------|------|------|
| `app/agents/design_agent.py` | 100% | Mock 实现，完全可测 |
| `app/agents/review_agent.py` | 100% | Mock 实现 |
| `app/agents/backend_agent.py` | 97% | 4 行未覆盖（异常分支） |
| `app/agents/frontend_agent.py` | 97% | 同上 |
| `app/agents/testing_agent.py` | 97% | 1 行未覆盖 |
| `app/core/config.py` | 100% | 配置类 |
| `app/foundation/llm/base.py` | 98% | LLM 抽象基类 |
| `app/core/logging.py` | 94% | 日志封装 |
| `app/api/main.py` | 90% | FastAPI app 入口 |

### 中等（60-89%）

| 模块 | 覆盖 | 主要缺失 |
|------|------|---------|
| `app/agents/base.py` | 79% | 错误处理 / experience 查询分支 |
| `app/orchestration/eventbus.py` | 76% | SSE 边角情况 |
| `app/orchestration/engine.py` | 75% | 重试/失败分支 |
| `app/orchestration/session.py` | 79% | 取消 / 错误恢复 |
| `app/foundation/git_repo.py` | 67% | rollback / log 格式 |
| `app/api/routes.py` | 63% | 部分 PUT/DELETE 路由 |
| `app/foundation/project.py` | 60% | 几个工具方法 |
| `app/orchestration/dynamic.py` | 59% | workflow selector 边角 |

### 较低（<60%）

| 模块 | 覆盖 | 原因 |
|------|------|------|
| `app/orchestration/workflows.py` | 89% | 几个边角分支 |
| `app/agents/deployment_agent.py` | 88% | M4-I2 验证异常分支 |
| `app/agents/requirements_agent.py` | 88% | Mock 边角 |
| `app/agents/types.py` | 91% | dataclass 方法 |
| `app/foundation/tools/base.py` | 86% | 工具注册 |
| `app/foundation/experience.py` | 48% | ChromaDB / 评分 / 毕业 |
| `app/foundation/tools/shell.py` | 51% | 实际 shell 命令执行 |
| `app/foundation/tools/file_ops.py` | 40% | 实际文件读写 |
| `app/foundation/tools/shell_run.py` | 37% | 长时进程 / 沙箱 |
| `app/foundation/llm/anthropic.py` | 31% | 真实 LLM 调用（需 API key） |
| `app/foundation/llm/openai.py` | 41% | 真实 LLM 调用（需 API key） |
| `app/core/sandbox.py` | 0% | Docker 沙箱（需 docker daemon） |

## 待补充测试（M4+）

| 任务 | 优先级 | 预期提升 |
|------|--------|----------|
| 经验库 ChromaDB 路径测试 | 中 | +5% |
| 工具真实执行测试（无 docker 沙箱） | 中 | +8% |
| Mock 真实 LLM Provider 响应 | 高 | +10% |
| Docker 沙箱集成测试（需 docker daemon） | 低 | +5% |
| 路由 PUT/DELETE 补全 | 低 | +3% |
| **预期总覆盖率（M4 末）** | | **~80%** |

## 怎么本地复现

```bash
cd backend
python3 -m pytest tests/ --cov=app --cov-report=term-missing

# HTML 报告
python3 -m pytest tests/ --cov=app --cov-report=html:htmlcov
open htmlcov/index.html
```

## 怎么集成到 CI

`.github/workflows/ci.yml` 当前已包含 `pytest` 步骤。要加覆盖率徽章：

```yaml
- name: Test with coverage
  run: |
    pip install pytest-cov
    pytest --cov=app --cov-report=xml --cov-report=term

- name: Upload to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

> 注：HTML 报告目录 `htmlcov/` 已被 `.gitignore` 排除。
