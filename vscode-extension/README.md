# 🌸 樱花小队 VS Code 插件

> 在 VS Code 中召唤你的 AI 多智能体虚拟团队。

## 简介

樱花小队 (SakuraAgentTeam) 是一个可视化 AI 多智能体协作平台。本插件让你无需离开 VS Code 即可：

- 浏览预设团队与专家列表
- 选择团队发起协作对话
- 实时查看 SSE 流式输出
- 一键打开网页版

## 功能

- **侧边栏团队视图**：列出所有预设团队，点击即可发起对话。
- **侧边栏专家视图**：浏览全部专家智能体。
- **Webview 聊天面板**：在 VS Code 内嵌的聊天界面与团队协作，支持 SSE 流式输出。
- **命令面板**：`🌸 樱花小队: 启动 / 对话 / 选择团队 / 打开网页版`。

## 安装

### 方式一：从 VSIX 安装

```bash
cd vscode-extension
npm install
npm run package      # 生成 sakura-agent-team-0.1.0.vsix
```

在 VS Code 中：

```
扩展面板 → ⋯ → 从 VSIX 安装 → 选择生成的 .vsix 文件
```

或命令行：

```bash
code --install-extension sakura-agent-team-0.1.0.vsix
```

### 方式二：开发调试

```bash
cd vscode-extension
npm install
# 用 VS Code 打开 vscode-extension/ 目录，按 F5 启动扩展开发宿主
```

## 配置

在 VS Code 设置中搜索 `樱花小队`，或编辑 `settings.json`：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `sakura.serverUrl` | `http://localhost:8000` | 后端 API 地址 |
| `sakura.token` | `""` | JWT 登录 Token（留空则匿名访问） |

## 命令

| 命令 | 说明 |
|------|------|
| `🌸 樱花小队: 启动` | 检查后端连接，刷新团队与专家列表 |
| `🌸 樱花小队: 对话` | 选择团队并打开聊天面板 |
| `🌸 樱花小队: 选择团队` | 快速选择团队 |
| `🌸 樱花小队: 打开网页版` | 在浏览器打开前端界面 |
| `🌸 樱花小队: 刷新团队` | 刷新侧边栏团队列表 |
| `🌸 樱花小队: 刷新专家` | 刷新侧边栏专家列表 |

## 后端依赖

插件需要后端服务运行中。启动后端：

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 填入 LLM API Key
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

调用的 API：

- `GET /api/v1/teams` — 团队列表
- `GET /api/v1/experts` — 专家列表
- `POST /api/v1/teams/{id}/chat` — 团队协作（SSE 流式）

## 相关文档

- [项目主页](https://github.com/wanan3847/SakuraAgentTeam)
- [安装指南](../docs/INSTALL.md)
- [CLI 使用指南](../docs/CLI.md)
- [VS Code 插件详细指南](../docs/VSCODE_EXTENSION.md)
- [Agent 创建指南](../docs/AGENT_GUIDE.md)
- [7 种协作模式](../docs/COLLABORATION_MODES.md)

## License

MIT
