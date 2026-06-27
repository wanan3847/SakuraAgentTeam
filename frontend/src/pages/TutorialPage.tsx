/**
 * TutorialPage — 教学中心
 *
 * 3 个 Tab：
 * - 创建 Agent：5 步表单提交审核
 * - 免费获取 Token：动态拉取 /api/v1/llm/providers/free，展示注册步骤
 * - 使用方法：6 个使用场景说明
 *
 * 设计原则：
 * - 动态拉取供应商数据（不再硬编码）
 * - 统一首字母色块（不用 emoji）
 * - 暖纸感配色（不用亮粉/亮紫）
 * - 排版层级建立视觉层次（不用渐变文字）
 */

import { Component, useEffect, useState, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, Check, ChevronRight, ChevronDown, ChevronUp, Loader2, LogIn, Plus, X,
  Sparkles, ExternalLink, KeyRound, MessageSquare, Copy, CheckCheck, Bug,
  Globe, Apple, Monitor, Terminal, Code2, Container, Download, GitBranch,
} from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import { useAuth } from '../contexts/AuthContext'
import { submitAgent } from '../lib/submissionApi'
import { fetchFreeProviders, type LLMProvider } from '../lib/providersApi'
import { openBugReport } from '../lib/feedback'

type Tab = 'create' | 'token' | 'usage' | 'download'

const TABS: { id: Tab; label: string }[] = [
  { id: 'create', label: '创建 Agent' },
  { id: 'token', label: '免费获取 Token' },
  { id: 'download', label: '下载安装' },
  { id: 'usage', label: '使用方法' },
]

const STEPS = [
  { id: 1, title: '了解 Agent 结构' },
  { id: 2, title: '填写基本信息' },
  { id: 3, title: '编写角色设定' },
  { id: 4, title: '选择技能' },
  { id: 5, title: '预览并提交' },
]

// 统一色板 — 暖色调，不用亮色
const AVATAR_COLORS = ['#C97B8A', '#6B8E6B', '#C4955E', '#8C4A57', '#6B655C', '#4A4540']
const CATEGORIES = [
  { id: 'creative', name: '创意' },
  { id: 'design', name: '设计' },
  { id: 'tech', name: '技术' },
  { id: 'research', name: '研究' },
  { id: 'strategy', name: '策略' },
  { id: 'qa', name: '质量' },
  { id: 'industry', name: '行业' },
]
const PRESET_SKILLS = ['写作', '分析', '调研', '编程', '设计', '校对', '翻译', '总结', '头脑风暴', '数据可视化', '项目管理', '沟通协调']

const EXAMPLES = {
  goal: '例如：帮助用户撰写高质量、有深度的分析报告，覆盖多角度观点。',
  backstory: '例如：你是一位拥有 10 年经验的研究员，擅长将复杂问题拆解为可执行步骤。',
  tagline: '例如：用逻辑和洞察点亮每一个决策。',
}

// 使用方法内容
const USAGE_SECTIONS = [
  {
    id: 'quickstart',
    title: '快速开始',
    items: [
      '访问首页，点击「开始协作」进入工作台',
      '选择一个预设团队，或点击「组建团队」自定义',
      '在对话框输入你的需求，例如「帮我写一份产品发布会文案」',
      '观察多位专家在同一对话框内讨论、追问、给出方案',
      '可随时切换团队、调整成员，或导出对话',
    ],
  },
  {
    id: 'choose-team',
    title: '如何选择团队',
    items: [
      '内容创作：选择「内容创作团队」，包含文案、策划、校对专家',
      '技术研发：选择「全栈开发团队」，覆盖前端、后端、测试',
      '商业分析：选择「商业分析团队」，包含市场、财务、战略专家',
      '学术研究：选择「学术研究团队」，包含文献综述、数据分析专家',
      '不确定时：使用「管家调度」模式，让主管自动分配',
    ],
  },
  {
    id: 'modes',
    title: '7 种协作模式说明',
    items: [
      '群聊模式（group）：所有专家在同一对话框自由讨论，适合头脑风暴',
      '流水线模式（pipeline）：按顺序依次发言，前一位输出作为后一位输入',
      '管家模式（master）：主管分析任务，召唤合适专家，整合成果',
      '共识模式（consensus）：专家讨论后达成一致结论',
      '并行模式（parallel）：多位专家同时处理，最后整合',
      '转交模式（handoff）：专家间互相转交任务，灵活协作',
      '状态图模式（graph）：自定义任务依赖关系，按 DAG 执行',
    ],
  },
  {
    id: 'custom-team',
    title: '如何组建自定义团队',
    items: [
      '进入「专家库」浏览 100 位专家',
      '点击专家卡片选择成员（可多选）',
      '点击「组建团队」按钮进入组建页面',
      '为团队命名、选择协作模式',
      '保存后即可在工作台使用',
    ],
  },
  {
    id: 'history',
    title: '如何查看历史记录',
    items: [
      '点击导航栏「历史」进入历史页面',
      '查看所有对话记录，按时间倒序排列',
      '点击任意记录可查看完整对话内容',
      '支持删除不需要的历史记录',
    ],
  },
  {
    id: 'export',
    title: '如何导出对话',
    items: [
      '在工作台对话界面，找到导出按钮',
      '支持三种格式：Markdown、JSON、纯文本',
      'Markdown 适合分享和阅读',
      'JSON 适合程序化处理',
      '纯文本适合复制到其他工具',
    ],
  },
]

// 下载安装 — 各种客户端
interface DownloadMethod {
  id: string
  title: string
  platform: string
  req?: string
  note?: string
  iconName: 'Globe' | 'Apple' | 'Monitor' | 'Terminal' | 'Code2' | 'Container' | 'Download' | 'GitBranch'
  blocks: { name: string; cmd: string; note?: string }[]
  verify: string
}

const DOWNLOAD_SECTIONS: DownloadMethod[] = [
  {
    id: 'web',
    title: 'Web 版(无需安装)',
    platform: '任意浏览器',
    iconName: 'Globe',
    blocks: [
      { name: '在线访问', cmd: 'https://team.041126.xyz' },
      { name: '本地开发', cmd: 'git clone https://github.com/wanan3847/SakuraAgentTeam.git\ncd SakuraAgentTeam && ./deploy.sh dev' },
    ],
    verify: '浏览器打开 https://team.041126.xyz,看到首页即成功。',
  },
  {
    id: 'oneclick',
    title: '一键安装脚本(推荐)',
    platform: 'macOS / Linux / Windows',
    req: '需先安装 git + python3.11+ + node18+',
    iconName: 'Download',
    blocks: [
      { name: 'macOS / Linux (curl)', cmd: 'curl -fsSL https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.sh | bash' },
      { name: 'macOS / Linux (wget)', cmd: 'wget -qO- https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.sh | bash' },
      { name: 'Windows PowerShell', cmd: 'irm https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.ps1 | iex' },
    ],
    verify: '脚本自动检查依赖 + 克隆代码 + 装 Python/Node 依赖 + 生成 .env,提示"🌸 安装完成!"即成功。',
  },
  {
    id: 'source',
    title: '源码安装',
    platform: '需要 Node 18+ 和 Python 3.11+',
    iconName: 'GitBranch',
    blocks: [
      { name: '克隆 + 启动', cmd: 'git clone https://github.com/wanan3847/SakuraAgentTeam.git\ncd SakuraAgentTeam\n./deploy.sh dev' },
      { name: '手动启动后端', cmd: 'cd backend && python3 -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\npython -m uvicorn app.api.main:app --reload --port 8000' },
      { name: '手动启动前端', cmd: 'cd frontend && npm install && npm run dev' },
    ],
    verify: '前端 http://localhost:5173 · 后端 http://localhost:8000/docs',
  },
  {
    id: 'docker',
    title: 'Docker',
    platform: 'Docker 24+ / Docker Compose v2',
    iconName: 'Container',
    blocks: [
      { name: 'docker compose 完整栈', cmd: 'git clone https://github.com/wanan3847/SakuraAgentTeam.git\ncd SakuraAgentTeam\n./deploy.sh prod' },
      { name: '手动 docker compose', cmd: 'cd SakuraAgentTeam/infra\ndocker compose up -d --build' },
    ],
    verify: 'curl http://localhost:8000/health  # 返回 {"status":"healthy"} 即成功',
  },
  {
    id: 'cli',
    title: 'CLI 命令行',
    platform: 'Python 3.11+ / 任意系统',
    iconName: 'Terminal',
    blocks: [
      { name: '从 wheel 安装(本机或 CI)', cmd: 'cd SakuraAgentTeam/backend\npython3 -m build --wheel\npip install --user dist/sakura_agent_team-0.2.0-py3-none-any.whl' },
      { name: '从源码开发模式安装', cmd: 'git clone https://github.com/wanan3847/SakuraAgentTeam.git\ncd SakuraAgentTeam/backend\npip install -e .' },
      { name: '启动 REPL', cmd: 'sakura' },
      { name: '   ↑ REPL 里输入 / 显示所有 25+ 命令,输入 task "你的需求" 开始任务', cmd: 'echo "无命令,纯 REPL 交互"' },
      { name: '直接运行', cmd: 'cd SakuraAgentTeam/backend\npython -m app.cli.main' },
    ],
    verify: 'sakura --version  (应输出 sakura 0.2.0)',
  },
  {
    id: 'macos',
    title: 'macOS 桌面端',
    platform: 'macOS 11+ (Big Sur)',
    req: 'Apple Silicon (M1/M2/M3/M4) 或 Intel x64;需要本机已装 Python 3.10+(应用首次启动会用 Python 兜底启动后端)',
    iconName: 'Apple',
    note: '⚠️ 桌面端是 UI 壳,内嵌后端通过 Python 兜底启动(PyInstaller 6.x 在 macOS 14+ arm64 有 silent fail 已知问题)。如果只是想用,推荐用上面的「Web 版」或「一键安装脚本」。',
    blocks: [
      { name: '1. 打开 .dmg 安装器', cmd: 'open release/SakuraAgentTeam-0.2.0-arm64.dmg' },
      { name: '2. 在打开的窗口里把 SakuraAgentTeam.app 拖到 Applications 文件夹', cmd: 'cp -R "/Volumes/SakuraAgentTeam 0.2.0/SakuraAgentTeam.app" /Applications/' },
      { name: '3. 启动应用', cmd: 'open /Applications/SakuraAgentTeam.app' },
      { name: '4. 如果系统提示「无法打开,因为它来自身份不明的开发者」,执行以下命令授权', cmd: 'xattr -cr /Applications/SakuraAgentTeam.app\nopen /Applications/SakuraAgentTeam.app' },
      { name: '5. 应用启动后会自检 Python 3.10+ 并启动后端(默认 18800 端口)', cmd: 'python3 --version\nbrew install python@3.12   # 如果没装 Python' },
    ],
    verify: '打开应用后看到樱花小队主界面即成功。也可以用 curl 验证后端:curl http://localhost:18800/health',
  },
  {
    id: 'windows',
    title: 'Windows 桌面端',
    platform: 'Windows 10/11 (x64)',
    req: '需要 Node 18+;桌面端是 UI 壳,内嵌后端通过 Python 3.10+ 兜底启动',
    iconName: 'Monitor',
    note: '当前没有预编译 .exe(在 Mac 上交叉编译需要 wine,生成的 .exe 缺数字签名会有 SmartScreen 警告)。下方提供 3 种可行方案。',
    blocks: [
      { name: '方案 A — 推荐:用 PowerShell 一键脚本跑 Web 版(0 依赖打包)', cmd: 'irm https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.ps1 | iex' },
      { name: '方案 B — 在 Windows 上自建 .exe 桌面端', cmd: 'cd SakuraAgentTeam\\desktop\nnpm install\nnpm run build:win' },
      { name: '方案 C — 用 GitHub Actions 跨平台 CI 自动构建', cmd: 'gh workflow run desktop-build.yml --ref main' },
      { name: '   ↑ 产物会在 https://github.com/wanan3847/SakuraAgentTeam/actions 下的 Artifacts 里', cmd: 'open https://github.com/wanan3847/SakuraAgentTeam/actions' },
      { name: 'WSL2 方案(纯 Linux 子系统)', cmd: 'wsl --install\nwsl -- curl -fsSL https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.sh | bash' },
    ],
    verify: 'Web 版:浏览器打开 http://localhost:5173 看到首页即成功。桌面端:双击 .exe 后看到樱花小队主界面。',
  },
  {
    id: 'linux',
    title: 'Linux 桌面端',
    platform: 'Ubuntu 22.04+ / Debian 12+ / Fedora 39+ / Arch',
    req: '需要 Node 18+ 和 Python 3.10+',
    iconName: 'Terminal',
    blocks: [
      { name: '一键脚本(推荐)', cmd: 'curl -fsSL https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.sh | bash' },
      { name: 'Docker', cmd: 'git clone https://github.com/wanan3847/SakuraAgentTeam.git\ncd SakuraAgentTeam/infra && docker compose up -d --build' },
      { name: '自建 AppImage', cmd: 'cd desktop && npm install && npm run build:linux' },
    ],
    verify: 'curl http://localhost:8000/health  (应返回 healthy)',
  },
  {
    id: 'vscode',
    title: 'VS Code 插件',
    platform: 'VS Code 1.85+',
    req: '需要先装 VS Code(https://code.visualstudio.com/)',
    iconName: 'Code2',
    blocks: [
      { name: '1. 本机构建 .vsix', cmd: 'cd vscode-extension\nnpm install\nnpx vsce package' },
      { name: '2. 方式 A — 在 VS Code 里从 VSIX 安装(推荐,不用命令行)', cmd: 'open -a "Visual Studio Code" vscode-extension/sakura-agent-team-0.2.0.vsix' },
      { name: '   ↑ VS Code 会自动弹出对话框,点「安装」即可', cmd: 'echo "无命令,纯 UI 操作"' },
      { name: '2. 方式 B — 命令行安装(需先把 code 命令加到 PATH)', cmd: 'code --install-extension vscode-extension/sakura-agent-team-0.2.0.vsix' },
      { name: '   ↑ 没装 code 命令的话:VS Code → Cmd+Shift+P → 「Shell Command: Install code command in PATH」', cmd: 'echo "无命令,在 VS Code 里操作"' },
      { name: '3. 配置后端地址', cmd: 'sakura.serverUrl: http://localhost:8000\nsakura.token: 你的 JWT token' },
    ],
    verify: '安装后在 VS Code 命令面板(Cmd/Ctrl+Shift+P)输入"樱花"看到命令即成功。',
  },
]

// ===== 错误边界：避免单个 Tab 抛错导致整页空白 =====

interface EBState { error: Error | null }
class TutorialErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[TutorialPage] runtime error:', error, info)
  }
  render() {
    if (this.state.error) {
      const msg = this.state.error.message || String(this.state.error)
      return (
        <div className="glass rounded-xl p-6 md:p-8 text-center animate-fade-in">
          <h2 className="font-display text-xl font-medium text-clay mb-2">页面渲染出错</h2>
          <p className="text-sm text-ink-muted mb-3">请刷新页面，或切换到其他 Tab 重试。</p>
          <code className="block text-left text-[11px] bg-bg-subtle border border-border rounded-md px-3 py-2 font-mono text-ink-soft break-all whitespace-pre-wrap">
            {msg}
          </code>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-4 px-4 py-2 rounded-md glass text-sm font-medium hover:bg-surface-hover"
          >
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function TutorialPage() {
  const [tab, setTab] = useState<Tab>('download')

  return (
    <div className="aurora-bg min-h-screen relative">
      <SakuraPetals count={3} />

      {/* 顶栏 */}
      <nav className="sticky top-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-muted hover:text-ink transition-colors">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回</span>
          </Link>
          <h1 className="font-display text-lg font-medium">教学中心</h1>
          <button
            onClick={() => openBugReport({ location: 'tutorial/nav' })}
            className="flex items-center gap-1.5 text-xs text-ink-faint hover:text-sakura-700 transition-colors"
            title="一键打开 GitHub Issue 页面"
          >
            <Bug className="w-3.5 h-3.5" /> 报告 Bug
          </button>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8 relative z-10">
        {/* Bug 反馈提示 banner */}
        <div className="mb-6 flex items-start gap-3 p-4 rounded-xl glass border border-border">
          <Bug className="w-4 h-4 text-sakura-700 flex-shrink-0 mt-0.5" />
          <div className="flex-1 text-xs text-ink-soft leading-relaxed">
            <p className="mb-1">
              遇到问题？点击右侧按钮一键打开 GitHub Issue 页面，会自动附上当前 URL / 浏览器 / 时间。
            </p>
            <p className="text-ink-faint font-mono">issues 模板: 描述 · 复现步骤 · 期望 vs 实际 · 环境 · 错误堆栈</p>
          </div>
          <button
            onClick={() => openBugReport({ location: `tutorial/${tab}`, hint: '教学中心异常' })}
            className="btn-gradient px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 flex-shrink-0"
          >
            <Bug className="w-3.5 h-3.5" /> 报告 Bug
          </button>
        </div>

        {/* Tab 切换 */}
        <div className="flex p-1 bg-surface rounded-lg mb-8 max-w-2xl mx-auto border border-border">
          {TABS.map((t) => {
            const isActive = tab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex-1 py-2.5 rounded-md text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-ink text-surface'
                    : 'text-ink-muted hover:text-ink'
                }`}
              >
                {t.label}
              </button>
            )
          })}
        </div>

        {/* Tab 内容 */}
        <TutorialErrorBoundary>
          {tab === 'create' && <CreateAgentTab />}
          {tab === 'token' && <FreeTokenTab />}
          {tab === 'usage' && <UsageTab />}
          {tab === 'download' && <DownloadTab />}
        </TutorialErrorBoundary>
      </div>
    </div>
  )
}

// ===== Tab 1: 创建 Agent =====

function CreateAgentTab() {
  const { user, token } = useAuth()
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // 表单数据
  const [agentId, setAgentId] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [avatarColor, setAvatarColor] = useState(AVATAR_COLORS[0])
  const [category, setCategory] = useState('creative')
  const [goal, setGoal] = useState('')
  const [backstory, setBackstory] = useState('')
  const [tagline, setTagline] = useState('')
  const [skills, setSkills] = useState<string[]>([])
  const [customSkill, setCustomSkill] = useState('')

  const toggleSkill = (s: string) => {
    setSkills((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s])
  }

  const addCustomSkill = () => {
    const s = customSkill.trim()
    if (!s) return
    if (!skills.includes(s)) setSkills((prev) => [...prev, s])
    setCustomSkill('')
  }

  const canGoNext = () => {
    if (step === 2) return agentId.trim() && name.trim() && role.trim()
    if (step === 3) return goal.trim() && backstory.trim() && tagline.trim()
    if (step === 4) return skills.length > 0
    return true
  }

  const handleSubmit = async () => {
    if (!token) return
    setSubmitting(true)
    setError('')
    try {
      const res = await submitAgent(token, {
        agent_id: agentId.trim(),
        agent_name: name.trim(),
        agent_role: role.trim(),
        agent_avatar: name.charAt(0).toUpperCase() || 'A',
        agent_color: avatarColor,
        agent_category: category,
        agent_tagline: tagline.trim(),
        agent_goal: goal.trim(),
        agent_backstory: backstory.trim(),
        agent_skills: skills,
      })
      if (res.success) {
        setSuccess(true)
      } else {
        setError(res.message || '提交失败')
      }
    } catch (e: any) {
      setError(e.message || '网络错误')
    } finally {
      setSubmitting(false)
    }
  }

  const reset = () => {
    setSuccess(false)
    setStep(1)
    setAgentId(''); setName(''); setRole('')
    setAvatarColor(AVATAR_COLORS[0]); setCategory('creative')
    setGoal(''); setBackstory(''); setTagline('')
    setSkills([]); setCustomSkill('')
    setError('')
  }

  // 未登录
  if (!user || !token) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="glass rounded-2xl p-10 max-w-md w-full text-center animate-fade-up">
          <div className="w-12 h-12 mx-auto mb-4 rounded-lg bg-bg-subtle border border-border flex items-center justify-center">
            <KeyRound className="w-5 h-5 text-ink-muted" />
          </div>
          <h2 className="font-display text-2xl font-medium mb-2">请先登录</h2>
          <p className="text-sm text-ink-muted mb-6">提交 Agent 需要先登录</p>
          <Link to="/auth" className="btn-gradient inline-flex items-center gap-2 px-6 py-3 rounded-md font-medium">
            <LogIn className="w-4 h-4" /> 去登录
          </Link>
        </div>
      </div>
    )
  }

  // 提交成功
  if (success) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="glass rounded-2xl p-10 max-w-md w-full text-center animate-fade-up">
          <div className="w-12 h-12 mx-auto mb-4 rounded-lg bg-sage-soft border border-sage-soft flex items-center justify-center">
            <Check className="w-5 h-5 text-sage" />
          </div>
          <h2 className="font-display text-2xl font-medium mb-2">提交成功</h2>
          <p className="text-sm text-ink-muted mb-6">
            你的 Agent「{name}」已提交，等待管理员审核。
            <br />审核通过后将出现在专家库中。
          </p>
          <div className="flex items-center justify-center gap-3">
            <button onClick={reset} className="px-5 py-2.5 rounded-md glass text-sm font-medium hover:bg-surface-hover transition-colors">
              再创建一个
            </button>
            <Link to="/agents" className="btn-gradient inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-medium">
              查看专家库
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
      {/* 左侧：步骤导航 */}
      <aside className="lg:col-span-1">
        <div className="glass rounded-xl p-4 lg:sticky lg:top-24">
          <div className="text-xs text-ink-faint mb-3 font-medium px-2 font-mono">教学步骤</div>
          <div className="space-y-1">
            {STEPS.map((s) => {
              const isActive = step === s.id
              const isDone = step > s.id
              return (
                <button
                  key={s.id}
                  onClick={() => setStep(s.id)}
                  className={`w-full text-left p-3 rounded-lg transition-all flex items-center gap-2.5 ${
                    isActive ? 'selected-ring bg-bg-subtle' : 'hover:bg-bg-subtle'
                  }`}
                >
                  <div
                    className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 text-xs font-mono font-medium ${
                      isDone
                        ? 'bg-sage text-surface'
                        : isActive
                        ? 'bg-ink text-surface'
                        : 'bg-bg-subtle text-ink-faint'
                    }`}
                  >
                    {isDone ? <Check className="w-3.5 h-3.5" /> : s.id}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`text-xs font-medium ${isActive ? 'text-ink' : 'text-ink-muted'}`}>
                      {s.title}
                    </div>
                  </div>
                  {isActive && <ChevronRight className="w-3.5 h-3.5 text-ink-muted flex-shrink-0" />}
                </button>
              )
            })}
          </div>
        </div>
      </aside>

      {/* 右侧：内容区 */}
      <main className="lg:col-span-3">
        <div className="glass rounded-xl p-6 md:p-8 animate-fade-in">
          {error && (
            <div className="mb-4 text-xs text-clay bg-clay-soft border border-clay-soft rounded-md px-3 py-2">
              {error}
            </div>
          )}

          {/* Step 1: 了解 Agent 结构 */}
          {step === 1 && (
            <div>
              <StepHeader num={1} title="了解 Agent 结构" desc="每个 Agent 由 4 件套组成，借鉴 CrewAI 设计理念" />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                <StructureCard title="role（角色）" desc="Agent 的身份定位，例如「文案撰写专家」「数据分析师」" />
                <StructureCard title="goal（目标）" desc="Agent 要达成的核心目标，决定其行为方向" />
                <StructureCard title="backstory（背景故事）" desc="Agent 的过往经历，影响其回答风格和专业领域" />
                <StructureCard title="skills（技能）" desc="Agent 擅长的具体能力，可多选" />
              </div>
              <div className="mt-6 bg-bg-subtle rounded-md p-4 text-xs text-ink-muted leading-relaxed border border-border">
                一个好的 Agent = 清晰的角色 + 明确的目标 + 丰富的背景 + 匹配的技能。接下来我们一步步填写。
              </div>
            </div>
          )}

          {/* Step 2: 填写基本信息 */}
          {step === 2 && (
            <div>
              <StepHeader num={2} title="填写基本信息" desc="给你的 Agent 起个名字，定个身份" />
              <div className="space-y-4 mt-6">
                <Field label="Agent ID" hint="唯一标识，英文+下划线，如 copywriter">
                  <input
                    value={agentId}
                    onChange={(e) => setAgentId(e.target.value)}
                    placeholder="copywriter"
                    className="w-full bg-surface rounded-md px-4 py-2.5 text-sm border border-border font-mono focus:border-ink-muted"
                  />
                </Field>
                <Field label="名称" hint="展示给用户的中文名">
                  <input
                    name="agent-display-name"
                    id="agent-display-name"
                    autoComplete="off"
                    data-form-type="other"
                    spellCheck={false}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="文案小能手"
                    className="w-full bg-surface rounded-md px-4 py-2.5 text-sm border border-border focus:border-ink-muted"
                  />
                </Field>
                <Field label="角色" hint="身份定位">
                  <input
                    name="agent-role"
                    id="agent-role"
                    autoComplete="off"
                    data-form-type="other"
                    spellCheck={false}
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    placeholder="资深文案撰写专家"
                    className="w-full bg-surface rounded-md px-4 py-2.5 text-sm border border-border focus:border-ink-muted"
                  />
                </Field>
                <Field label="头像色" hint="首字母色块的颜色">
                  <div className="flex flex-wrap gap-2">
                    {AVATAR_COLORS.map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => setAvatarColor(c)}
                        className={`w-9 h-9 rounded-md transition-all ${avatarColor === c ? 'selected-ring' : 'border border-border'}`}
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </div>
                </Field>
                <Field label="分类" hint="所属领域">
                  <div className="flex flex-wrap gap-2">
                    {CATEGORIES.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setCategory(c.id)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all border ${
                          category === c.id
                            ? 'bg-ink text-surface border-ink'
                            : 'bg-surface text-ink-muted border-border hover:border-ink-muted'
                        }`}
                      >
                        {c.name}
                      </button>
                    ))}
                  </div>
                </Field>
              </div>
            </div>
          )}

          {/* Step 3: 编写角色设定 */}
          {step === 3 && (
            <div>
              <StepHeader num={3} title="编写角色设定" desc="定义 Agent 的灵魂：目标、背景、口号" />
              <div className="space-y-4 mt-6">
                <Field label="目标 (goal)" hint={EXAMPLES.goal}>
                  <textarea
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder={EXAMPLES.goal}
                    rows={3}
                    className="w-full bg-surface rounded-md px-4 py-2.5 text-sm border border-border focus:border-ink-muted resize-none"
                  />
                </Field>
                <Field label="背景故事 (backstory)" hint={EXAMPLES.backstory}>
                  <textarea
                    value={backstory}
                    onChange={(e) => setBackstory(e.target.value)}
                    placeholder={EXAMPLES.backstory}
                    rows={4}
                    className="w-full bg-surface rounded-md px-4 py-2.5 text-sm border border-border focus:border-ink-muted resize-none"
                  />
                </Field>
                <Field label="口号 (tagline)" hint={EXAMPLES.tagline}>
                  <input
                    value={tagline}
                    onChange={(e) => setTagline(e.target.value)}
                    placeholder={EXAMPLES.tagline}
                    className="w-full bg-surface rounded-md px-4 py-2.5 text-sm border border-border focus:border-ink-muted"
                  />
                </Field>
              </div>
            </div>
          )}

          {/* Step 4: 选择技能 */}
          {step === 4 && (
            <div>
              <StepHeader num={4} title="选择技能" desc="选择 Agent 擅长的能力，可多选或自定义" />
              <div className="mt-6">
                <div className="flex flex-wrap gap-2 mb-4">
                  {PRESET_SKILLS.map((s) => {
                    const isSelected = skills.includes(s)
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() => toggleSkill(s)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1 border ${
                          isSelected
                            ? 'bg-ink text-surface border-ink'
                            : 'bg-surface text-ink-muted border-border hover:border-ink-muted'
                        }`}
                      >
                        {isSelected && <Check className="w-3 h-3" />} {s}
                      </button>
                    )
                  })}
                </div>
                {/* 自定义技能 */}
                <div className="flex gap-2">
                  <input
                    name="custom-skill"
                    id="custom-skill"
                    autoComplete="off"
                    data-form-type="other"
                    spellCheck={false}
                    value={customSkill}
                    onChange={(e) => setCustomSkill(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomSkill() } }}
                    placeholder="自定义技能..."
                    className="flex-1 bg-surface rounded-md px-4 py-2 text-sm border border-border focus:border-ink-muted"
                  />
                  <button
                    type="button"
                    onClick={addCustomSkill}
                    className="btn-gradient px-4 rounded-md text-sm font-medium flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> 添加
                  </button>
                </div>
                {/* 已选自定义技能 */}
                {skills.filter((s) => !PRESET_SKILLS.includes(s)).length > 0 && (
                  <div className="mt-3">
                    <div className="text-[11px] text-ink-faint mb-2 font-mono">自定义技能</div>
                    <div className="flex flex-wrap gap-2">
                      {skills.filter((s) => !PRESET_SKILLS.includes(s)).map((s) => (
                        <span key={s} className="px-3 py-1 rounded-md text-xs bg-bg-subtle text-ink-soft border border-border flex items-center gap-1">
                          {s}
                          <button onClick={() => toggleSkill(s)} className="hover:text-clay">
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="mt-4 text-xs text-ink-faint font-mono">
                  已选 {skills.length} 项技能
                </div>
              </div>
            </div>
          )}

          {/* Step 5: 预览并提交 */}
          {step === 5 && (
            <div>
              <StepHeader num={5} title="预览并提交" desc="检查 Agent 卡片，确认无误后提交审核" />
              <div className="mt-6 max-w-sm mx-auto">
                <AgentPreviewCard
                  name={name || '未命名 Agent'}
                  role={role || '未填写角色'}
                  color={avatarColor}
                  category={CATEGORIES.find((c) => c.id === category)?.name || category}
                  tagline={tagline || '未填写口号'}
                  skills={skills}
                />
              </div>
              {/* 详细信息 */}
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
                <PreviewBlock label="目标" content={goal} />
                <PreviewBlock label="背景故事" content={backstory} />
              </div>
            </div>
          )}

          {/* 底部导航 */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-border">
            <button
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              disabled={step === 1}
              className="px-5 py-2.5 rounded-md glass text-sm font-medium disabled:opacity-40 hover:bg-surface-hover transition-colors"
            >
              上一步
            </button>
            {step < 5 ? (
              <button
                onClick={() => canGoNext() && setStep((s) => Math.min(5, s + 1))}
                disabled={!canGoNext()}
                className="btn-gradient px-6 py-2.5 rounded-md text-sm font-medium flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                下一步 <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="btn-gradient px-6 py-2.5 rounded-md text-sm font-medium flex items-center gap-1.5 disabled:opacity-60"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                提交审核
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

// ===== Tab 2: 免费获取 Token（动态拉取） =====

function FreeTokenTab() {
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const data = await fetchFreeProviders()
        if (!cancelled) setProviders(data || [])
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="text-center py-20 text-ink-faint text-sm">
        <Loader2 className="w-5 h-5 animate-spin mx-auto mb-3" />
        加载免费供应商列表…
      </div>
    )
  }

  if ((providers || []).length === 0) {
    return (
      <div className="text-center py-20 text-ink-faint text-sm">
        暂无免费供应商数据，请稍后再试。
      </div>
    )
  }

  return (
    <div>
      <div className="text-center mb-8">
        <h2 className="font-display text-2xl font-medium mb-2">免费获取 Token</h2>
        <p className="text-sm text-ink-muted max-w-xl mx-auto">
          以下是提供免费额度的 LLM 供应商，注册即可获得 token 用于体验。
          点击卡片查看详细信息和配置方法。
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {(providers || []).map((p, i) => {
          const expanded = expandedId === p.id
          return (
            <div
              key={p.id}
              className="glass rounded-xl p-4 animate-fade-up cursor-pointer"
              style={{ animationDelay: `${i * 0.03}s` }}
              onClick={() => setExpandedId(expanded ? null : p.id)}
            >
              {/* 头部 — 纯文字,不要图标 */}
              <div className="flex items-start justify-between mb-3">
                <span className="badge badge-success">免费</span>
              </div>

              <h3 className="font-medium text-sm mb-1">{p.name}</h3>
              <p className="text-xs text-ink-muted leading-relaxed mb-3">
                {p.free_tier_desc || '提供免费额度'}
              </p>

              <div className="flex items-center justify-between text-[11px] text-ink-faint font-mono">
                <span>{p.models.length} 个模型</span>
                <a
                  href={p.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center gap-1 text-ink-muted hover:text-ink"
                >
                  注册链接 <ExternalLink className="w-3 h-3" />
                </a>
              </div>

              {/* 展开详情 */}
              {expanded && (
                <div className="mt-4 pt-4 border-t border-border space-y-3 animate-fade-in" onClick={(e) => e.stopPropagation()}>
                  {/* base_url */}
                  <div>
                    <div className="text-[10px] text-ink-faint mb-1 font-mono">Base URL</div>
                    <code className="block text-[11px] bg-bg-subtle rounded-md px-3 py-2 font-mono text-ink-soft break-all border border-border">
                      {p.base_url}
                    </code>
                  </div>

                  {/* 推荐模型 */}
                  {(p.models || []).length > 0 && (
                    <div>
                      <div className="text-[10px] text-ink-faint mb-1.5 font-mono">推荐模型</div>
                      <div className="flex flex-wrap gap-1">
                        {(p.models || []).slice(0, 6).map((m, j) => (
                          <span
                            key={j}
                            className="text-[10px] px-2 py-0.5 rounded bg-bg-subtle text-ink-muted border border-border font-mono"
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 配置说明 */}
                  <div>
                    <div className="text-[10px] text-ink-faint mb-1 font-mono">配置方法</div>
                    <p className="text-[11px] text-ink-muted bg-bg-subtle rounded-md px-3 py-2 leading-relaxed border border-border">
                      前往「<Link to="/providers" className="text-ink underline underline-offset-2">供应商</Link>」页面，
                      找到 <span className="font-medium text-ink-soft">{p.name}</span>，填入你的 API Key 即可。
                      你的 Key 只属于你自己，不会共享。
                    </p>
                  </div>
                </div>
              )}

              {/* 展开提示 */}
              <div className="mt-3 flex items-center justify-center text-[10px] text-ink-faint font-mono">
                {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                <span className="ml-1">{expanded ? '收起' : '查看详情'}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* 提示 */}
      <div className="mt-6 glass rounded-md p-4 flex items-start gap-2 text-xs text-ink-muted">
        <Sparkles className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-ink-faint" />
        <div className="leading-relaxed">
          提示：免费额度有限，建议优先尝试 DeepSeek、智谱 GLM、SiliconFlow 等国内供应商，
          注册流程更简单。配置完成后前往「<Link to="/providers" className="text-ink underline underline-offset-2">供应商管理</Link>」保存 API Key。
        </div>
      </div>
    </div>
  )
}

// ===== Tab 3: 使用方法 =====

function UsageTab() {
  return (
    <div>
      <div className="text-center mb-8">
        <h2 className="font-display text-2xl font-medium mb-2">使用方法</h2>
        <p className="text-sm text-ink-muted max-w-xl mx-auto">
          从快速开始到高级用法，全面了解樱花小队的协作能力。
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {USAGE_SECTIONS.map((s, i) => (
          <div
            key={s.id}
            className="glass rounded-xl p-5 animate-fade-up"
            style={{ animationDelay: `${i * 0.05}s` }}
          >
            <div className="flex items-center gap-3 mb-3">
              <span className="num-badge">/0{i + 1}</span>
              <h3 className="font-medium text-sm">{s.title}</h3>
            </div>
            <ul className="space-y-2">
              {s.items.map((it, j) => (
                <li key={j} className="flex items-start gap-2 text-xs text-ink-muted leading-relaxed">
                  <span className="w-1 h-1 rounded-full bg-ink-faint flex-shrink-0 mt-1.5" />
                  <span>{it}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="mt-8 glass-dark rounded-xl p-8 text-center">
        <h3 className="font-display text-xl font-medium text-surface mb-2">
          准备好开始了吗？
        </h3>
        <p className="text-surface/60 text-xs mb-5">立即体验虚拟团队的协作魅力</p>
        <Link to="/workspace" className="btn-gradient inline-flex items-center gap-2 px-6 py-2.5 rounded-md text-sm font-medium">
          <MessageSquare className="w-4 h-4" /> 进入工作台
        </Link>
      </div>
    </div>
  )
}

// ===== Tab 4: 下载安装 =====

const ICON_MAP = { Globe, Apple, Monitor, Terminal, Code2, Container, Download, GitBranch }

function CmdBlock({ name, cmd, note }: { name: string; cmd: string; note?: string }) {
  const [copied, setCopied] = useState(false)
  const onCopy = () => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(cmd).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-ink-soft">{name}</span>
        <button
          onClick={onCopy}
          className="text-ink-faint hover:text-ink transition-colors flex items-center gap-1 text-[10px] font-mono"
          aria-label="复制命令"
        >
          {copied ? <CheckCheck className="w-3 h-3 text-sage" /> : <Copy className="w-3 h-3" />}
          {copied ? '已复制' : '复制'}
        </button>
      </div>
      <pre className="bg-bg-subtle border border-border rounded-md px-3 py-2.5 overflow-x-auto text-xs leading-relaxed font-mono text-ink whitespace-pre">
        <code>{cmd}</code>
      </pre>
      {note && <p className="text-[10px] text-ink-faint mt-1.5 font-mono">// {note}</p>}
    </div>
  )
}

function DownloadTab() {
  return (
    <div>
      <div className="text-center mb-8">
        <h2 className="font-display text-2xl font-medium mb-2">下载安装</h2>
        <p className="text-sm text-ink-muted max-w-xl mx-auto">
          9 种方式覆盖所有平台 — Web、桌面、CLI、VS Code、Docker，挑一种你顺手的就行。
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {DOWNLOAD_SECTIONS.map((s, i) => {
          const Icon = ICON_MAP[s.iconName]
          return (
            <div
              key={s.id}
              className="glass rounded-xl p-5 animate-fade-up"
              style={{ animationDelay: `${i * 0.04}s` }}
            >
              <div className="flex items-start gap-3 mb-4">
                <span className="num-badge flex-shrink-0">
                  <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
                </span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm text-ink mb-0.5">{s.title}</h3>
                  <p className="text-[11px] text-ink-faint font-mono">
                    {s.platform}{s.req ? ` · ${s.req}` : ''}
                  </p>
                </div>
              </div>
              {s.note && (
                <div className="mb-3 px-3 py-2 rounded-md bg-clay/8 border border-clay/20">
                  <p className="text-[11px] text-clay leading-relaxed">{s.note}</p>
                </div>
              )}
              <div>
                {s.blocks.map((b, j) => (
                  <CmdBlock key={j} name={b.name} cmd={b.cmd} note={b.note} />
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-border">
                <p className="text-[11px] text-ink-muted leading-relaxed">
                  <span className="text-sage font-mono mr-1">✓</span>{s.verify}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      {/* GitHub Release 通用入口 */}
      <div className="mt-6 glass rounded-md p-5 flex flex-col md:flex-row items-start md:items-center gap-4 justify-between">
        <div>
          <h4 className="text-sm font-medium text-ink mb-1">找不到你系统的安装包？</h4>
          <p className="text-xs text-ink-muted">所有平台的最新构建都在 GitHub Release 统一发布。</p>
        </div>
        <a
          href="https://github.com/wanan3847/SakuraAgentTeam/releases"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-gradient px-5 py-2 rounded-md text-sm font-medium inline-flex items-center gap-2 flex-shrink-0"
        >
          <ExternalLink className="w-3.5 h-3.5" /> GitHub Release
        </a>
      </div>
    </div>
  )
}

// ===== 共享子组件 =====

function Avatar({ name }: { name: string }) {
  const initial = name.charAt(0).toUpperCase()
  return (
    <div className="w-10 h-10 rounded-md flex items-center justify-center font-mono font-semibold text-sm text-ink-soft bg-bg-subtle border border-border flex-shrink-0">
      {initial}
    </div>
  )
}

function StepHeader({ num, title, desc }: { num: number; title: string; desc: string }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="num-badge">/0{num}</span>
        <h2 className="font-display text-xl font-medium">{title}</h2>
      </div>
      <p className="text-sm text-ink-muted ml-9">{desc}</p>
    </div>
  )
}

function StructureCard({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="bg-bg-subtle rounded-md p-4 border border-border">
      <span className="font-mono text-sm font-medium text-ink-soft block mb-2">{title}</span>
      <p className="text-xs text-ink-muted leading-relaxed">{desc}</p>
    </div>
  )
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-xs font-medium text-ink-soft">{label}</label>
        {hint && <span className="text-[10px] text-ink-faint font-mono">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function PreviewBlock({ label, content }: { label: string; content: string }) {
  return (
    <div className="bg-bg-subtle rounded-md p-3 border border-border">
      <div className="text-[11px] text-ink-faint mb-1.5 font-mono">{label}</div>
      <p className="text-xs text-ink-muted leading-relaxed">{content || '未填写'}</p>
    </div>
  )
}

function AgentPreviewCard({
  name, role, color, category, tagline, skills,
}: {
  name: string; role: string; color: string; category: string; tagline: string; skills: string[]
}) {
  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-start justify-between mb-3">
        <div
          className="w-12 h-12 rounded-md flex items-center justify-center text-lg font-mono font-semibold text-surface flex-shrink-0"
          style={{ backgroundColor: color }}
        >
          {name.charAt(0).toUpperCase()}
        </div>
        <span className="badge">{category}</span>
      </div>
      <h3 className="font-medium text-base mb-0.5">{name}</h3>
      <p className="text-xs text-ink-faint mb-2 font-mono">{role}</p>
      <p className="text-sm text-ink-muted leading-relaxed mb-3">{tagline}</p>
      <div className="flex flex-wrap gap-1">
        {skills.slice(0, 5).map((s, j) => (
          <span key={j} className="text-[10px] px-2 py-0.5 rounded bg-bg-subtle text-ink-muted border border-border font-mono">
            {s}
          </span>
        ))}
        {skills.length > 5 && (
          <span className="text-[10px] px-2 py-0.5 rounded bg-bg-subtle text-ink-faint border border-border font-mono">
            +{skills.length - 5}
          </span>
        )}
      </div>
    </div>
  )
}
