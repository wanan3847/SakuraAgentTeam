# VS Code 插件指南

> 在 VS Code 中召唤你的 AI 多智能体虚拟团队。

---

## 目录

1. [简介](#1-简介)
2. [安装](#2-安装)
3. [配置](#3-配置)
4. [侧边栏视图](#4-侧边栏视图)
5. [命令](#5-命令)
6. [聊天面板](#6-聊天面板)
7. [开发调试](#7-开发调试)
8. [FAQ](#8-faq)

---

## 1. 简介

樱花小队 VS Code 插件让你无需离开编辑器即可：

- 在侧边栏浏览预设团队与专家列表
- 选择团队发起协作对话
- 在 Webview 聊天面板中实时查看 SSE 流式输出
- 一键打开网页版

---

## 2. 安装

### 方式一：从 VSIX 安装

```bash
cd vscode-extension
npm install
npm run package    # 生成 sakura-agent-team-0.1.0.vsix
```

在 VS Code 中安装：

1. 打开扩展面板（`Cmd+Shift+X` / `Ctrl+Shift+X`）
2. 点击右上角 `⋯` → 「从 VSIX 安装」
3. 选择生成的 `.vsix` 文件

或命令行安装：

```bash
code --install-extension sakura-agent-team-0.1.0.vsix
```

### 方式二：开发调试

```bash
cd vscode-extension
npm install
```

用 VS Code 打开 `vscode-extension/` 目录，按 `F5` 启动扩展开发宿主。

---

## 3. 配置

在 VS Code 设置中搜索「樱花小队」，或编辑 `settings.json`：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `sakura.serverUrl` | string | `http://localhost:8000` | 后端 API 地址 |
| `sakura.token` | string | `""` | JWT 登录 Token（留空则匿名访问） |

### settings.json 示例

```json
{
  "sakura.serverUrl": "http://localhost:8000",
  "sakura.token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### 获取 Token

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "your_name", "password": "your_password"}'

# 登录获取 token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your_name", "password": "your_password"}'
```

返回的 `access_token` 填入 `sakura.token` 配置。

---

## 4. 侧边栏视图

安装后，左侧活动栏会出现樱花图标 🌸。点击展开两个视图：

### 团队视图 (`sakura.teams`)

列出所有预设团队。每个团队显示：
- 图标 + 名称
- 协作模式（group / pipeline / master 等）

操作：
- **点击团队** → 打开聊天面板
- **右键团队** → 「对话」或「选择团队」
- **标题栏刷新按钮** → 重新加载团队列表

### 专家视图 (`sakura.agents`)

列出所有专家智能体。每个专家显示：
- 头像 + 名称
- 职业角色

操作：
- **标题栏刷新按钮** → 重新加载专家列表

---

## 5. 命令

通过命令面板（`Cmd+Shift+P` / `Ctrl+Shift+P`）调用：

| 命令 | 说明 |
|------|------|
| `🌸 樱花小队: 启动` | 检查后端连接，刷新团队与专家列表 |
| `🌸 樱花小队: 对话` | 选择团队并打开聊天面板 |
| `🌸 樱花小队: 选择团队` | 快速选择团队 |
| `🌸 樱花小队: 打开网页版` | 在浏览器打开前端界面 |
| `🌸 樱花小队: 刷新团队` | 刷新侧边栏团队列表 |
| `🌸 樱花小队: 刷新专家` | 刷新侧边栏专家列表 |

---

## 6. 聊天面板

点击团队后，VS Code 会打开一个 Webview 聊天面板。

### 界面

- **顶部**：团队名称、协作模式、成员列表
- **中部**：消息流（用户消息 + 专家发言）
- **底部**：输入框 + 发送按钮

### 使用

1. 在输入框输入消息
2. 按回车或点击「发送」
3. 团队成员依次发言，实时流式显示
4. 发送按钮在等待回复期间禁用

### SSE 事件

插件通过 `POST /api/v1/teams/{id}/chat` 接收 SSE 流，处理以下事件：

| 事件 | 说明 |
|------|------|
| `agent_message` / `agent_speak` | 专家发言内容 |
| `error` | 错误信息 |

---

## 7. 开发调试

### 项目结构

```
vscode-extension/
├── package.json       # 插件清单
├── extension.js       # 主入口
├── sakura.svg         # 活动栏图标
├── README.md          # 插件说明
├── CHANGELOG.md       # 变更日志
└── .vscodeignore      # 打包排除规则
```

### 调试步骤

1. 用 VS Code 打开 `vscode-extension/` 目录
2. 按 `F5` 启动扩展开发宿主
3. 在开发宿主中测试插件功能
4. 修改代码后重新加载（`Cmd+R` / `Ctrl+R`）

### 打包

```bash
npm run package
# 生成 sakura-agent-team-0.1.0.vsix
```

---

## 8. FAQ

### Q: 侧边栏显示「无法连接后端」？

A: 确认后端服务已启动：

```bash
curl http://localhost:8000/health
```

如果后端地址不是 `http://localhost:8000`，在设置中修改 `sakura.serverUrl`。

### Q: 聊天没有回复？

A: 检查：
1. 后端是否配置了 LLM API Key（`backend/.env`）
2. `sakura.token` 是否有效（如需登录）
3. 后端日志是否有报错

### Q: 如何在远程开发中使用？

A: 在远程 SSH / WSL / 容器环境中，确保后端服务可达。修改 `sakura.serverUrl` 指向后端地址。

### Q: 插件支持哪些团队？

A: 插件通过 `GET /api/v1/teams` 获取后端配置的所有预设团队。团队列表与网页版一致，详见 [AGENT_GUIDE.md](./AGENT_GUIDE.md)。

---

## 相关文档

- [安装指南](./INSTALL.md)
- [CLI 使用指南](./CLI.md)
- [Agent 创建指南](./AGENT_GUIDE.md)
- [7 种协作模式](./COLLABORATION_MODES.md)
- [项目主页](https://github.com/wanan3847/SakuraAgentTeam)
