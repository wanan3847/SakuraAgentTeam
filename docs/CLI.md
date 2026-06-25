# CLI 使用指南

> 樱花小队命令行客户端 `sakura`，在终端调度多智能体工作流。

---

## 目录

1. [安装](#1-安装)
2. [配置](#2-配置)
3. [命令总览](#3-命令总览)
4. [config — 配置管理](#4-config--配置管理)
5. [task — 提交任务](#5-task--提交任务)
6. [sessions — 会话列表](#6-sessions--会话列表)
7. [status — 会话详情](#7-status--会话详情)
8. [logs — 事件流跟踪](#8-logs--事件流跟踪)
9. [artifacts — 查看产物](#9-artifacts--查看产物)
10. [cancel — 取消会话](#10-cancel--取消会话)
11. [projects — 项目管理](#11-projects--项目管理)
12. [providers — LLM 供应商](#12-providers--llm-供应商)
13. [doctor — 诊断](#13-doctor--诊断)
14. [repl — 交互式 REPL](#14-repl--交互式-repl)
15. [version — 版本](#15-version--版本)

---

## 1. 安装

```bash
pip install sakura-agent-team
```

或从源码安装：

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam/backend
pip install -e .
```

---

## 2. 配置

CLI 配置文件位于 `~/.sakura/config.toml`，首次使用时自动生成。

```bash
sakura config show
```

---

## 3. 命令总览

```
sakura <command> [options]

命令：
  config      管理配置（api_url / token / workflow / output）
  task        提交新任务（自动启动工作流）
  sessions    列出所有会话
  status      查看会话详情
  logs        流式跟踪会话事件
  artifacts   列出会话产物
  cancel      取消会话
  projects    列出项目
  providers   列出 LLM 供应商
  doctor      诊断连接 / 健康检查
  repl        交互式 REPL
  version     打印版本
```

---

## 4. config — 配置管理

### 显示当前配置

```bash
sakura config show
```

### 更新配置

```bash
sakura config set \
  --api-url http://localhost:8000 \
  --token <your_jwt_token> \
  --workflow full_greenfield \
  --output table
```

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--api-url` | 后端 API 地址 | `http://localhost:8000` |
| `--token` | JWT 登录 Token | `""` |
| `--workflow` | 默认工作流 | `full_greenfield` |
| `--output` | 输出格式 `table` / `json` | `table` |

### 查看配置文件路径

```bash
sakura config path
```

---

## 5. task — 提交任务

提交一个需求，自动启动多智能体工作流并实时跟踪进度。

```bash
sakura task "帮我设计一个登录页面" \
  --project my-app \
  --workflow full_greenfield
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--project` | `-p` | 关联项目 ID |
| `--workflow` | `-w` | 工作流：`full_greenfield` / `brownfield` / `incremental` |
| `--no-wait` | — | 提交后不跟踪进度 |
| `--output` | `-o` | 输出格式 |

示例：

```bash
# 提交后自动跟踪进度（默认）
sakura task "实现一个待办事项 API"

# 只提交，不跟踪
sakura task "写一篇技术博客" --no-wait
```

跟踪过程中按 `Ctrl+C` 可中断跟踪，任务仍在后台运行。

---

## 6. sessions — 会话列表

列出所有会话：

```bash
sakura sessions
sakura sessions --output json
```

---

## 7. status — 会话详情

查看单个会话的详细状态：

```bash
sakura status <session_id>
```

持续刷新直到完成：

```bash
sakura status <session_id> --watch
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--watch` | `-w` | 持续刷新直到完成 |
| `--output` | `-o` | 输出格式 |

---

## 8. logs — 事件流跟踪

实时流式打印会话事件（SSE），按 `Ctrl+C` 退出：

```bash
sakura logs <session_id>
```

输出为 JSON Lines 格式，每行一个事件：

```json
{"event": "agent_started", "data": {"agent_role": "requirements_agent"}}
{"event": "agent_completed", "data": {"agent_role": "requirements_agent"}}
{"event": "session_completed", "data": {}}
```

---

## 9. artifacts — 查看产物

列出某会话的所有产物（代码、文档、设计稿等）：

```bash
sakura artifacts <session_id>
sakura artifacts <session_id> --output json
```

---

## 10. cancel — 取消会话

取消一个进行中的会话：

```bash
sakura cancel <session_id>
```

---

## 11. projects — 项目管理

列出所有项目：

```bash
sakura projects
```

---

## 12. providers — LLM 供应商

列出支持的 LLM 供应商：

```bash
# 常用 24 个
sakura providers

# 全部 100+（需要安装 litellm）
sakura providers --full
```

---

## 13. doctor — 诊断

检查 API 连通性与配置：

```bash
sakura doctor
```

输出示例：

```
API URL: http://localhost:8000
配置文件: ~/.sakura/config.toml (存在)
✓ 后端健康: {'status': 'ok'}
```

---

## 14. repl — 交互式 REPL

启动 Claude Code 风格的交互式终端：

```bash
sakura repl
```

REPL 内支持：

- 直接输入需求 → 7 Agent 协作生成全栈代码
- `/task` — 提交任务
- `/status` — 查看状态
- `/tokens` — Token 监视
- `/agents` — 列出专家
- `/skills` — 列出技能
- `/mcp` — MCP 工具
- `/artifacts` — 查看产物
- `/env` — 环境信息
- `/help` — 帮助
- `/exit` — 退出

---

## 15. version — 版本

```bash
sakura version
```

输出：

```
sakura 0.1.0
```

---

## 输出格式

所有命令支持 `--output` / `-o` 参数切换输出格式：

| 格式 | 说明 | 适用场景 |
|------|------|----------|
| `table` | 表格（默认） | 人工阅读 |
| `json` | JSON | 脚本处理 / 管道 |

```bash
sakura sessions -o json | jq '.[0].id'
```

---

## 环境变量

CLI 也支持通过环境变量配置，优先级低于配置文件：

| 变量 | 说明 |
|------|------|
| `SAKURA_API_URL` | 后端 API 地址 |
| `SAKURA_TOKEN` | JWT Token |
| `SAKURA_OUTPUT` | 输出格式 |

```bash
export SAKURA_API_URL=http://localhost:8000
sakura sessions
```
