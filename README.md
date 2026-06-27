# 樱花小队 SakuraAgentTeam

> 一个可视化 AI 多智能体协作平台，支持 100+ 位虚拟专家、7 种协作模式、Artifact 产物链、**每位用户用自己的 LLM Key**。
> 借鉴 CrewAI / AG2 / Anthropic / MetaGPT / OpenAI Swarm / LangGraph 等成熟框架的能力。

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![React](https://img.shields.io/badge/react-18-61dafb)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](https://fastapi.tiangolo.com)
[![VS Code](https://img.shields.io/badge/VS%20Code-插件-007ACC)](./vscode-extension)

- **GitHub**：<https://github.com/wanan3847/SakuraAgentTeam>
- **在线体验**：<https://team.041126.xyz>
- **免费获取 Token 教程**：[http://localhost:5173/tutorial](http://localhost:5173/tutorial)（启动后访问）
- **友情链接**(放最下面,免得抢正文章节的位置):
  - <https://041126.xyz/>
  - <https://blog.041126.xyz/>
  - <https://anime.041126.xyz/>

---

## 一句话介绍

> **100 个专家 + 254 个 LLM 供应商 + 7 种协作模式 + Artifact 产物链 = 你的私人 AI 团队,每个人的 key 自己做主。**

- **100+ 预设专家**:覆盖 30 个分类(创意/设计/技术/研究/策略/审核/行业/教育/金融/法律/健康/媒体/音乐/写作/数据/DevOps/商业/学术/翻译/电商/游戏/旅游/美食/体育/农业/能源/航空/环保/社交/心理)
- **254 个 LLM 供应商**:OpenAI / Anthropic / DeepSeek / Qwen / 智谱 / Kimi / Ollama / 自定义 OpenAI 兼容端点,**每个用户自带 Key**
- **7 种协作模式**:群聊 / 流水线 / 管家 / 共识 / 并行 / 转交 / 状态图
- **9 支预设团队**:开箱即用,涵盖营销 / 内容 / 研发 / 研究 / 创业 / 品牌 / 产品 / 并行工程 / 论文写作
- **强制最终成果**:每次协作都会生成 `final_deliverable`,LLM 失败也有 fallback 汇总,不只停留在聊天记录
- **多端接入**:Web / VS Code 插件 / CLI / 桌面应用
- **每用户独立 LLM**:你的 key 你的对话,token 走你自己的账户

---

## 5 分钟跑通

### 1. 一键启动(推荐)

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
./deploy.sh dev
```

浏览器打开 <http://localhost:5173>。

> 不填 LLM Key 也能跑 —— 后端会用 mock,Agent 走离线分支。**强烈建议** 至少配一个 Key,体验真实对话。

### 2. 配自己的 LLM Key

启动后:

1. 注册账号(用户名 / 邮箱 / 密码)
2. 顶栏点头像 → 「我的 LLM」→ 「添加 LLM 配置」
3. 选厂商(254 个里挑一个) → 填 `base_url` / `api_key` / `model`
4. 「测试连接」 ✓ → 「保存」 → 设为「默认」
5. 进首页选个团队 → 发消息
6. 第一个 SSE 事件会显示 **🟢 你的 DeepSeek · deepseek-chat**,说明你的 key 真的生效

> 详细流程见 [docs/USER_LLM.md](./docs/USER_LLM.md)。

### 3. CLI 一行

```bash
pip install sakura-agent-team
sakura login
sakura llm-save --provider openai --base-url https://api.deepseek.com/v1 \
                --api-key sk-... --model deepseek-chat --default
sakura task "帮我写一份 LLM provider 调研"
```

---

## 功能特性

### 核心:用户自带 LLM Key(★)

- **真用你的 key**:每次对话都用你自己保存的 `api_key`,SSE 第一个事件会显示用的是哪家的 key。
- **254 个供应商**:从 OpenAI 到 Ollama,从 DeepSeek 到自建中转,全部 OpenAI 兼容,一行配置。
- **per-user engine**:每个用户独立一个 `CollaborationEngine`,互不干扰,token 走你自己的账户。
- **多配置切换**:可以配多个 LLM,日常用便宜的,关键时刻切到 Claude。
- **CLI `sakura me-llm`**:随时查看"我的对话正在用谁的 key"。

详见 [docs/USER_LLM.md](./docs/USER_LLM.md)。

### 100+ 专家 / 7 种协作模式 / Artifact 产物链

- **100+ 位预设专家智能体**:覆盖 30 个分类,详细列表见 [docs/AGENT_GUIDE.md](./docs/AGENT_GUIDE.md)。
- **7 种协作模式**(借鉴业界成熟框架):
  - 群聊 (group) — 顺序发言
  - 流水线 (pipeline) — 接力产出
  - 管家 (master) — 主管委派(借鉴 CrewAI Hierarchical)
  - 共识 (consensus) — 群聊共识(借鉴 AG2 GroupChat)
  - 并行 (parallel) — 并行执行(借鉴 Anthropic Orchestrator-Workers)
  - 转交 (handoff) — Agent 互转(借鉴 OpenAI Swarm)
  - 状态图 (graph) — DAG 任务图(借鉴 LangGraph)
- **9 支预设团队**:开箱即用,营销 / 内容 / 研发 / 研究 / 创业 / 品牌 / 产品 / 并行工程 / 论文写作。
- **可视化团队组建**:界面上挑专家、配协作模式、即时预览拓扑。
- **统一协作状态**:任务图、任务状态、Agent 产物、最终交付物都落在 `CollaborationState`。
- **结构化产物**:每个任务节点至少生成一个 Artifact,下游 Agent 直接读取上游 Artifact,不是只看聊天历史。
- **最终整合器**:Finalizer 消费全部 Artifact,生成可直接导出/复用的最终报告。
- **质量控制**:输出太短会自动补充,缺少必要章节会触发一次修正。

### 实时 & 工具

- **实时 SSE 流式输出**:每个 Agent 的发言、思考、产物都通过 Server-Sent Events 实时推送。
- **共享白板**:借鉴 MetaGPT 产物链,团队成员共享一块白板,沉淀中间产物与最终交付物。
- **任务图执行**:借鉴 LangGraph,DAG 节点按依赖推进,状态包括 `pending / ready / running / done / failed / skipped`。
- **执行追踪**:借鉴 Smolagents Trace,完整记录每一步 Agent 调用、工具使用、上下文流转。
- **10 个内置工具**:file_edit / shell / grep / glob / web_search / web_scraper / mcp 等。
- **11 个内置 Skill**:generate_fullstack / diagnose / tdd / prototype / pdf / to_prd / caveman / 等。

### 多端接入

- **Web 网页版** — React 18 + Vite + Tailwind,🌸 高级感视觉风格
- **VS Code 插件** — 侧边栏 + Webview,直接在 IDE 里召唤团队
- **CLI 命令行** — Typer,25+ 命令,完整 REPL,跨平台
- **桌面应用** — Electron,macOS / Windows / Linux 安装包

### 用户 & 社区

- **JWT 注册登录**:区分匿名用户与登录用户。
- **历史记录**:登录用户可查看、检索、续接过往的协作会话。
- **Agent 社区提交**:用户提交 → 管理员审核 → 通过后加入 Agent 库,社区共建专家生态。
- **教程页**:免费获取 Token 教程 + Agent 创建教程。

---

## 一键安装

### 方式一:pip 安装(推荐)

```bash
pip install sakura-agent-team
```

安装后即可使用 `sakura` 命令行工具。

### 方式二:一键脚本

**macOS / Linux**:
```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
./scripts/install.sh
```

**Windows (PowerShell)**:
```powershell
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
.\scripts\install.ps1
```

### 方式三:源码安装

```bash
git clone https://github.com/wanan3847/SakuraAgentTeam.git
cd SakuraAgentTeam
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

> 详细安装说明见 [docs/INSTALL.md](./docs/INSTALL.md)。

---

## 快速开始

### 启动后端

```bash
cd backend
cp .env.example .env   # 填入 LLM API Key(可选)
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 启动前端

```bash
cd frontend
npm run dev
```

浏览器访问 <http://localhost:5173>,后端 API 文档 <http://localhost:8000/docs>。

### 一键启动

```bash
./deploy.sh dev
```

---

## CLI 使用

```bash
# 配置
sakura config set --api-url http://localhost:8000 --token <your_token>

# 提交任务
sakura task "帮我设计一个登录页面"

# 查看会话
sakura sessions
sakura status <session_id>
sakura logs <session_id>

# LLM 管理
sakura me-llm                  # 看我现在用谁的 key
sakura llm-save --provider ... # 配一个新 LLM
sakura llm-list                # 列出所有 LLM 配置
sakura llm-set-default <id>    # 切默认

# 交互式 REPL(输入 / 显示所有命令菜单)
sakura repl
```

> 完整 CLI 文档见 [docs/CLI.md](./docs/CLI.md)。

---

## VS Code 插件

```bash
cd vscode-extension
npm install
npm run package   # 生成 .vsix 安装包
```

然后在 VS Code 扩展面板「从 VSIX 安装」即可。

功能:
- 侧边栏团队 / 专家列表
- Webview 聊天面板(SSE 流式)
- 一键打开网页版

> 详细说明见 [docs/VSCODE_EXTENSION.md](./docs/VSCODE_EXTENSION.md)。

---

## 桌面应用

樱花小队提供桌面应用(基于 Electron),支持 macOS / Windows / Linux:

```bash
cd desktop
npm install
npm run build   # 打包
```

> 桌面应用打包产物见 [GitHub Releases](https://github.com/wanan3847/SakuraAgentTeam/releases)。

---

## 100+ Agent 列表

樱花小队内置 100 位预设专家,覆盖 30 个分类:

| 分类 | 数量 | 代表专家 |
|------|------|----------|
| 创意 (creative) | 4 | 文案、主笔、小说家、诗人 |
| 设计 (design) | 4 | 视觉、交互、插画、动效 |
| 技术 (tech) | 7 | 全栈、前端、后端、AI 工程、数据、运维、安全 |
| 研究 (research) | 4 | 行研、数据科学、用户研究、产品经理 |
| 策略 (strategy) | 7 | 增长、战略、商务、销售、财务、运营、项目 |
| 审核 (qa) | 2 | 审核、测试 |
| 行业 (industry) | 12 | 法务、私教、教授、翻译、公关、演讲、健康、职涯、SaaS、教育、金融、医疗 |
| 教育 (education) | 3 | 在线教师、课程设计师、教育顾问 |
| 金融 (finance) | 3 | 财务顾问、投资分析师、会计 |
| 法律 (legal) | 2 | 法律顾问、合同审查 |
| 健康 (healthcare) | 2 | 健康顾问、心理咨询师 |
| 媒体 (media) | 3 | 视频编导、播客制作人、摄影师 |
| 音乐 (music) | 2 | 音乐制作人、作曲家 |
| 写作 (writing) | 3 | 小说家、剧本作家、诗人 |
| 数据 (data) | 3 | 数据科学家、数据工程师、ML 工程师 |
| DevOps (devops) | 3 | DevOps 工程师、SRE、安全工程师 |
| 商业 (business) | 3 | 商业顾问、项目经理、运营经理 |
| 学术 (academic) | 7 | 文献调研、方法设计、数据分析、论文写作、编辑润色、项目管理、论文审查 |
| 翻译 (translation) | 3 | 英文翻译、日文翻译、多语种翻译 |
| 电商 (ecommerce) | 3 | 电商运营、选品专家、直播策划 |
| 游戏 (game) | 3 | 游戏设计师、游戏开发、游戏剧情 |
| 旅游 (travel) | 2 | 旅行规划师、旅游文案 |
| 美食 (food) | 2 | 菜谱开发、美食评论 |
| 体育 (sports) | 2 | 运动教练、体育分析 |
| 农业 (agriculture) | 2 | 农业技术、园艺师 |
| 能源 (energy) | 2 | 新能源、电力系统 |
| 航空 (aerospace) | 2 | 航空工程、无人机 |
| 环保 (environment) | 2 | 环境工程、碳中和 |
| 社交 (social) | 2 | 社交媒体、社群运营 |
| 心理 (psychology) | 1 | 职业规划 |

> 完整 Agent 列表与创建指南见 [docs/AGENT_GUIDE.md](./docs/AGENT_GUIDE.md)。

---

## 254 个 LLM 供应商

通过 LiteLLM 一行接入 254 个 LLM 供应商,详细配置见 [docs/USER_LLM.md](./docs/USER_LLM.md)。

| 类型 | 代表供应商 |
|------|-----------|
| 协议类 | OpenAI、Anthropic |
| 云平台 | AWS Bedrock、Google Vertex AI、Azure OpenAI |
| 国产 | DeepSeek、通义千问 Qwen、智谱 GLM、Kimi、零一万物、火山引擎豆包、腾讯混元、百度千帆 |
| 主流第三方 | Google Gemini、Mistral、Cohere、Groq、Together AI、OpenRouter、Fireworks AI、DeepInfra |
| 本地 | Ollama、vLLM、任意 OpenAI 兼容端点 |

启动后访问 `GET /api/v1/llm/providers` 看完整列表,或在 Web 端 ProvidersPage 浏览配置。

---

## 在线版本与真实数据

线上体验地址：<https://team.041126.xyz>

首页指标不使用写死的营销数字,而是从 `GET /api/v1/public/stats` 读取真实数据:

| 指标 | 数据来源 |
|------|----------|
| 累计完成任务 | 历史会话表 `conversations` |
| 在线智能体 | 后端实际注册的核心 Agent |
| 累计节省工时 | 根据真实消息量估算 |
| 社区贡献者 | 活跃用户数 + 已通过 Agent 投稿数 |
| LLM 供应商 | 后端 provider registry 实际长度 |

生产部署采用 PM2 + Nginx + Cloudflare Tunnel:

- 后端：`uvicorn app.api.main:app --host 127.0.0.1 --port 8000`
- 前端：`frontend/dist` 由 Nginx 静态托管
- Tunnel：`team.041126.xyz -> http://localhost:5173`
- 部署脚本：[scripts/deploy-to-team.sh](./scripts/deploy-to-team.sh)

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy / SQLite / SSE |
| 前端 | React 18 / TypeScript / Tailwind CSS / Vite / 🌸 暖纸感视觉风格 |
| LLM | OpenAI 兼容 API + LiteLLM(254 个供应商) |
| CLI | Typer / Rich |
| VS Code 插件 | Node.js / VS Code Extension API |
| 桌面 | Electron |

---

## 项目结构

```
SakuraAgentTeam/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── agents/           # 100+ Agent 定义 + 注册表
│   │   ├── api/              # HTTP / SSE 路由
│   │   ├── auth/             # JWT 用户认证
│   │   ├── core/             # 配置 / 日志 / 沙箱
│   │   ├── foundation/       # LLM / 工具 / 技能 / MCP
│   │   ├── history/          # 历史记录
│   │   ├── llm_providers/    # 254 个 LLM 供应商 + per-user 配置
│   │   ├── orchestration/    # 7 种协作引擎 + Artifact / DAG / Finalizer
│   │   ├── collaboration/    # 协作 session / task / artifact 持久化
│   │   └── submissions/      # Agent 社区提交
│   ├── cli/                  # 命令行客户端(25+ 命令)
│   └── tests/                # pytest 测试
├── frontend/                 # React + Vite 前端
│   └── src/
│       ├── pages/            # 10 个页面
│       ├── components/       # CountUp / SakuraPetals / ...
│       └── contexts/         # React Context
├── vscode-extension/         # VS Code 插件
├── desktop/                  # 桌面应用
├── docs/                     # 文档
│   ├── INSTALL.md            # 安装指南
│   ├── CLI.md                # CLI 使用
│   ├── VSCODE_EXTENSION.md   # VS Code 插件
│   ├── AGENT_GUIDE.md        # Agent 创建指南
│   ├── COLLABORATION_MODES.md # 7 种协作模式
│   ├── ARCHITECTURE.md       # 后端架构
│   ├── USER_LLM.md           # 用户 LLM Key 流程
│   └── OPENDESIGN_REFERENCE.md # opendesign 风格参考(待重设计用)
├── infra/                    # Docker Compose / 沙箱镜像
├── scripts/                  # 安装 / 启动脚本
└── deploy.sh                 # 一键部署
```

---

## API 文档

启动后端后访问 <http://localhost:8000/docs> 查看 Swagger 文档。

主要接口:

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/experts` | 获取所有专家 |
| GET | `/api/v1/experts/categories` | 获取所有分类 |
| GET | `/api/v1/teams` | 获取预设团队 |
| POST | `/api/v1/teams` | 创建自定义团队 |
| POST | `/api/v1/teams/{id}/chat` | 团队协作(SSE 流式,per-user LLM) |
| POST | `/api/v1/teams/{id}/graph` | 状态图模式(LangGraph 风格) |
| POST | `/api/v1/teams/{id}/handoff` | Handoff 模式(Swarm 风格) |
| GET | `/api/v1/collaboration/{session_id}/state` | 协作状态(任务图 + 产物) |
| GET | `/api/v1/collaboration/{session_id}/artifacts` | 协作产物列表 |
| GET | `/api/v1/collaboration/{session_id}/final` | 最终交付物 |
| GET | `/api/v1/public/stats` | 首页真实统计 |
| GET | `/api/v1/llm/providers` | 254 个供应商列表 |
| GET | `/api/v1/llm/configs` | 我的 LLM 配置 |
| POST | `/api/v1/llm/configs` | 保存 LLM 配置 |
| POST | `/api/v1/llm/test-connection` | 测试连接 |
| GET | `/api/v1/me/llm-config` | 我现在用的 LLM |
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录 |
| GET | `/api/v1/history` | 历史记录 |
| POST | `/api/v1/submissions` | 提交 Agent |

---

## 借鉴的业界框架

| 框架 | 借鉴点 |
|------|--------|
| CrewAI | Agent 4 件套 (role / goal / backstory / skills) + ProcessType |
| AG2 (AutoGen) | GroupChatManager + 智能选择发言者 |
| Anthropic Multi-Agent | Orchestrator-Workers 并行模式 |
| MetaGPT | 共享白板产物链 |
| OpenAI Swarm | Handoff 转交模式 |
| LangGraph | 任务状态机 (DAG + Checkpoint) |
| Smolagents | Agent Trace 执行追踪 |
| LiteLLM | 254 个 LLM 供应商一行接入 |

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/INSTALL.md](./docs/INSTALL.md) | 安装指南(pip / 源码 / macOS / Windows / Docker / VS Code) |
| [docs/DEPLOY.md](./docs/DEPLOY.md) | **生产部署指南**(Linux VPS / Nginx / HTTPS / 备份 / 监控) |
| [docs/CLI.md](./docs/CLI.md) | CLI 命令行使用指南(25+ 命令) |
| [docs/VSCODE_EXTENSION.md](./docs/VSCODE_EXTENSION.md) | VS Code 插件指南 |
| [docs/AGENT_GUIDE.md](./docs/AGENT_GUIDE.md) | Agent 创建指南 + 100+ 专家完整列表 |
| [docs/COLLABORATION_MODES.md](./docs/COLLABORATION_MODES.md) | 7 种协作模式详解 |
| [docs/AGENT_COLLABORATION_REWORK_PLAN.md](./docs/AGENT_COLLABORATION_REWORK_PLAN.md) | 子 Agent 协作改造方案(任务图 / Artifact / Finalizer) |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 后端架构(per-user engine / SSE / framework 借鉴) |
| [docs/USER_LLM.md](./docs/USER_LLM.md) | 用户 LLM Key 流程(配 Key → 验证 → 排错) |
| [docs/OPENDESIGN_REFERENCE.md](./docs/OPENDESIGN_REFERENCE.md) | opendesign 风格前端参考手册(待重设计用) |
| [docs/CONTEST_POST.md](./docs/CONTEST_POST.md) | TRAE AI 创造力大赛参赛帖草稿 |
| [CHANGELOG.md](./CHANGELOG.md) | 变更日志 |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | 贡献指南 |
| [LICENSE](./LICENSE) | MIT 协议 |

---

## 友情链接

(放最下面,不抢正文章节)

- <https://041126.xyz/>
- <https://blog.041126.xyz/>
- <https://anime.041126.xyz/>

---

## License

[MIT](./LICENSE) © 2026 wanan3847
