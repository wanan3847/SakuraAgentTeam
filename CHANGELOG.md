# Changelog

SakuraAgentTeam 项目的所有重要变更记录。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased] — 2026-06-25

### ✨ 新增

#### 头像上传功能
- 新增 `POST /api/v1/auth/me/avatar` — multipart/form-data 上传头像图片,返回 data: URL 直接 `<img src>` 显示
- 后端限制:2MB,PNG/JPEG/WebP/GIF,存储到 `data/avatars/{user_id}_{timestamp}.{ext}`
- `User.avatar` 字段从 `String(10)` 改为 `Text`,支持存颜色 hex / emoji / data: URL
- 前端 AccountPage 新增上传 UI:点击「上传图片」按钮 → 选择文件 → 预览 → 上传 → 自动刷新
- UserCard 和修改头像区同时支持显示图片 / 颜色 / emoji 三种头像格式
- 修复 `changePassword` API 调用路径(`POST /auth/change-password` 而非 `PUT /auth/password`)
- 修复 `fetchMyStats` API 调用路径(`GET /auth/stats` 而非 `GET /auth/me/stats`)

#### 下载页面修复(诚实化)
- 删除所有假的 GitHub Release 链接(dmg/exe/AppImage/vsix)
- 删除所有不存在的包管理器引用(PyPI/Homebrew/winget/Scoop/Chocolatey/AUR/Flatpak)
- 新增 `scripts/install.sh` — macOS/Linux 一键安装脚本(检查依赖 → 克隆 → 装 Python/Node 依赖 → 生成 .env)
- 新增 `scripts/install.ps1` — Windows PowerShell 一键安装脚本
- `DOWNLOAD_SECTIONS` 重写为 9 个**实际可用**的下载方法:Web / 一键脚本 / 源码 / Docker / CLI / macOS(开发中) / Windows(开发中) / Linux / VS Code(开发中)
- 在线访问地址改为 `https://team.041126.xyz`

#### 供应商配置 autofill 修复
- ProvidersPage 搜索框 `type="text"` → `type="search"`(Chrome 不会 autofill search 类型)
- ProvidersPage 供应商详情卡片 6 个 input 全部加 `name` / `id` / `autoComplete="off"` / `data-form-type="other"` / `data-lpignore="true"` / `spellCheck={false}`
- 自定义端点弹窗 4 个 input 同样处理
- 密码类型 input 改用 `autoComplete="new-password"` 抑制 Chrome 自动填 admin

#### team.041126.xyz 部署脚本
- 新增 `scripts/deploy-to-team.sh` — team.041126.xyz 专用部署脚本(8 步:SSH 检查 → Docker → Nginx → 克隆 → .env → Docker 启动 → Nginx 反代 → HTTPS 证书)
- 目标服务器:47.103.96.182 (公) / 172.24.21.218 (私)
- ping 测试 0.28ms 可达,curl 返回 502(Nginx 已运行,无上游)
- 脚本语法检查通过(`bash -n`)

#### Bug 反馈入口
- 新增 `frontend/src/lib/feedback.ts` — `openBugReport()` / `openFeatureRequest()`,生成带 URL/UA/时间/堆栈的 GitHub Issue 链接,`window.open` 一键跳转
- `HomePage.tsx` 页脚新增「报告 Bug」按钮(lucide `Bug` 图标)
- `TutorialPage.tsx` 顶栏右侧 + 顶部 banner 双入口,带 issue 模板说明(描述 / 复现 / 期望 vs 实际 / 环境 / 错误堆栈)

#### 教学中心修复
- `TutorialPage.tsx` 修复 4 个 Tab 都正常渲染(create / token / usage / **download**),default tab 改为 `download`
- 加 `TutorialErrorBoundary` 类组件包裹 4 个 Tab,任何子组件抛错会在 UI 显示具体 `error.message`,浏览器 console 打 `[TutorialPage] runtime error: ...`,不再整页空白

#### Favicon 真实 🌸 emoji
- 用 PIL + macOS Apple Color Emoji 字体渲染 🌸 emoji → 多尺寸 PNG/ICO
- 7 个 `<link rel="icon">` 引用(ico / 32 / 48 / 96 / 192 / svg / apple-touch-icon)
- PIL 像素采样确认彩色位图正确嵌入

#### HomePage 实时指标仪表盘
- 新增 `frontend/src/components/CountUp.tsx` — `requestAnimationFrame + easeOutCubic` 1800ms 数字滚动动画,`IntersectionObserver` 进入视口触发,千分位,后缀,前缀全支持。StrictMode 双 mount 兼容(cleanup reset `startedRef`)
- HomePage 5 张指标卡片(12,510 / 5 / 38,540 / 100+ / 254+),每张含 `+Δ%` 增量徽章(sage 绿)、1px 强调色边线、live 呼吸点

#### 核心:用户 LLM Key 真的被使用
- **核心 Bug 修复**:之前 chat 路由统一用 `OPENAI_API_KEY`(.env 里的开发者共享 key),**没有**走用户自己保存的 key
- 新增 `backend/app/llm_providers/async_helpers.py` — `build_llm_for_user_async(user_id)` 异步为指定用户构建 LLM provider,优先用 `is_default=True & is_active=True` 的 `CustomProvider`,否则退回最新激活配置
- 新增 `backend/app/orchestration/agent_team.py` — `get_engine_for_user_async(user_id)` 为每个用户独立维护一个 `CollaborationEngine`,互不干扰
- 改造 `backend/app/api/teams.py` — 4 个 chat 路由(`/chat`、`/chat/sync`、`/handoff`、`/graph`)全部接受 `user: User = Depends(get_current_user)`,**真的**用用户自己存的 LLM key
- 改造 SSE 流式:第一个事件固定为 `event: llm_info`,data 包含 `source: user|shared`, `display_name`, `provider_id`, `model`, `base_url`, `has_api_key`,告诉前端「这次对话用谁的 key」
- 新增 `GET /api/v1/me/llm-config` — 前端「我的 LLM」页面用
- 新增 CLI 命令 `sakura me-llm` — CLI 用户也能查自己用的 LLM

#### 前端打磨
- 樱花背景 emoji 黑块修复 — `SakuraPetals.tsx` 完全重写为纯 CSS 圆点(4 种暖色 `#C97B8A / #F5E6E9 / #9A5A68 / #E8B5BE`),`position: fixed` + `filter: blur(0.3px)` 柔化
- 详情弹窗右上角「A」修复 — `AgentLibraryPage.tsx` 替换 `✕` Unicode 字符为 lucide `<X />` 图标,`strokeWidth 1.5`
- 输入框自动填 admin 修复 — `AuthPage.tsx` 3 个 input 加 `name` / `id` / `autoComplete`(注册用 `new-password`,登录用 `current-password`)属性
- 供应商去图标 — `AgentLibraryPage.tsx` / `TeamBuilderPage.tsx` 分类标签去掉 emoji `{c.icon}`,只保留文字
- ProvidersPage 三步上手 CTA — 头部加「01 选厂商 → 02 填 Key → 03 用起来」引导,卡片加 `cursor-pointer` + `hover:border-ink-muted` + 右侧「点击配置」徽章

#### 部署准备
- 新增 `docs/DEPLOY.md` — 12 节生产部署指南(VPS 选型 / 5 分钟 Docker / Nginx + Let's Encrypt / 密钥 / 备份 / 升级 / 监控 / 性能 / 安全清单 / 一键脚本 / 反馈)
- 新增 `infra/nginx-sakura.conf` — 反代 + HTTPS + HSTS + SSE 300s timeout 模板,一行 `certbot --nginx` 完成证书
- `backend/.env.example` 增补 `SECRET_KEY`(JWT 签名,生成命令 `openssl rand -hex 32`)+ `HOST`/`PORT` + CORS 注释
- `deploy.sh` 支持 `dev` / `prod` / `sandbox` / `stop` / `logs` / `clean` 6 个子命令,Docker 模式持续运行

#### 新文档
- `docs/OPENDESIGN_REFERENCE.md` — opendesign 风格前端设计参考手册,10 节,含色彩 token、字体加载、8 个组件契约、4 个页面 mockup、动画契约、落地清单
- `docs/ARCHITECTURE.md` — 后端架构(per-user engine / SSE / agent framework 借鉴)
- `docs/USER_LLM.md` — 用户 LLM key 流程详解(为什么需要、怎么用、怎么排查)
- `docs/DEPLOY.md` — 生产部署指南(本文)
- `CHANGELOG.md` — 本文件
- `LICENSE` — MIT 协议文本

### 🧹 清理
- 删除未跟踪的 `reference/` 目录(253MB)
- 删除未跟踪的 `skills/gstack/` 目录(1.1GB)
- 把根目录 `skills/`(100MB,165 个 SKILL.md 文档)加入 `.gitignore`(本地保留,IDE 参考用)
- 删除 HomePage 废弃的 `_LEGACY_STATS` 块,避免 lint 警告
- 根目录 `sakura-premium-redesign.html`(opendesign 参考)加入 `.gitignore`,不污染 git 仓库
- 整理 `CHANGELOG.md` 重复的 Unreleased 段,合并为单段

### ✅ 验证
- 前端 TypeScript `npx tsc --noEmit` 通过
- 后端 `pytest tests/` 67 个测试全过
- 后端 `auth routes` 7 个路由加载成功(含新 `/me/avatar`)
- 10 个前端路由全部 200
- 254 个供应商 API 返回正常
- `/me/llm-config` 返回 `source=user`, `display_name=我的 DeepSeek`
- chat SSE 第一个事件:`{"source": "user", "display_name": "我的 DeepSeek", "model": "deepseek-chat"}`
- CLI `me-llm` 输出「你的对话正在使用你自己保存的 LLM 配置」
- 100 个专家 / 30 个分类 / 9 个预设团队 API 全部正常
- Vite 构建成功(322.70KB JS / 28.02KB CSS / 91.12KB gzip)
- 服务器 47.103.96.182 ping 可达,HTTP 502(Nginx 待配置上游)
- `bash -n scripts/install.sh && bash -n scripts/deploy-to-team.sh` 语法检查通过

---

## 历史版本

### v0.1.0 — 2026-06-23

首版发布,包含:

- 100+ 预设专家智能体,30 个分类(创意/设计/技术/研究/策略/审核/行业/教育/金融/法律/健康/媒体/音乐/写作/数据/DevOps/商业/学术/翻译/电商/游戏/旅游/美食/体育/农业/能源/航空/环保/社交/心理)
- 7 种协作模式(借鉴 CrewAI/AG2/Anthropic/MetaGPT/OpenAI Swarm/LangGraph/Smolagents)
- 9 支预设团队
- 可视化团队组建器
- 实时 SSE 流式输出
- 100+ LLM 供应商(LiteLLM)
- 多端接入:Web / VS Code 插件 / CLI / 桌面应用(Electron)
- 用户注册登录(JWT)
- 历史记录
- Agent 社区提交

---

## 贡献者

- 项目维护者:[@wanan3847](https://github.com/wanan3847)
- 贡献方式:见 [CONTRIBUTING.md](./CONTRIBUTING.md)

---

## 协议

本项目采用 [MIT](./LICENSE) 协议。
