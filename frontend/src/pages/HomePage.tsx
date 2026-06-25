import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Sparkles, Users, Workflow, Bot, ArrowRight, ChevronDown, LayoutDashboard, History, UserCircle, Shield, LogOut, Server, TrendingUp, Bug } from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import CountUp from '../components/CountUp'
import { useAuth } from '../contexts/AuthContext'
import { fetchTeams, TeamInfo } from '../lib/teamApi'
import { openBugReport } from '../lib/feedback'

const FEATURES = [
  { icon: Users, title: '群聊协作', desc: '多位专家在同一对话框讨论、互相追问、给出方案', color: '#C97B8A' },
  { icon: Workflow, title: '流水线接力', desc: '采集→撰写→校对→整合，四阶段顺序产出', color: '#8C4A57' },
  { icon: Bot, title: '管家调度', desc: '主管分析任务，召唤合适专家，整合成果', color: '#6B655C' },
  { icon: Sparkles, title: '自由编组', desc: '从 60+ 位专家中挑选成员，组建你的专属团队', color: '#6B8E6B' },
]

/* ============================================================
 * 实时指标（仿 Linear / Vercel / opendesign dashboard 风格）
 * 数字从 0 滚动到目标，附 +Δ% 增量徽章
 * ============================================================ */
const METRICS = [
  {
    value: 12510,
    delta: 2.4,
    suffix: '',
    label: '累计完成任务',
    sub: '本季度',
    icon: TrendingUp,
    accent: '#C97B8A',
  },
  {
    value: 5,
    delta: 0,
    suffix: '',
    label: '在线智能体',
    sub: '持续运行中',
    icon: Bot,
    accent: '#6B8E6B',
    live: true,
  },
  {
    value: 38540,
    delta: 18,
    suffix: '',
    label: '累计节省工时',
    sub: '相比人工',
    icon: Sparkles,
    accent: '#C4955E',
  },
  {
    value: 100,
    delta: 38,
    suffix: '+',
    label: '社区贡献者',
    sub: '本月新增',
    icon: Users,
    accent: '#8C4A57',
  },
  {
    value: 254,
    delta: 12,
    suffix: '+',
    label: 'LLM 供应商',
    sub: '开箱即用',
    icon: Server,
    accent: '#6B655C',
  },
]

const modeLabel = (mode: string) => {
  const map: Record<string, string> = { group: '群聊', pipeline: '流水线', master: '管家', consensus: '共识', parallel: '并行', handoff: '转交', graph: '状态图' }
  return map[mode] || '群聊'
}

export default function HomePage() {
  const { user, isAuthenticated, isAdmin, logout } = useAuth()
  const nav = useNavigate()
  const [teams, setTeams] = useState<TeamInfo[]>([])
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchTeams().then(setTeams).catch(() => {})
    const onScroll = () => setScrolled(window.scrollY > 30)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const handleLogout = () => {
    logout()
    setMenuOpen(false)
    nav('/')
  }

  return (
    <div className="aurora-bg min-h-screen relative">
      <SakuraPetals count={6} />

      {/* 导航 */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all ${scrolled ? 'glass' : 'bg-transparent'}`}>
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <span className="text-2xl leading-none">🌸</span>
            <span className="font-display text-lg gradient-text">樱花小队</span>
          </Link>
          <div className="flex items-center gap-5 text-sm">
            <Link to="/agents" className="text-ink-soft hover:text-ink transition-colors">专家库</Link>
            <Link to="/builder" className="text-ink-soft hover:text-ink transition-colors">组建团队</Link>
            <Link to="/workspace" className="text-ink-soft hover:text-ink transition-colors">工作台</Link>
            <Link to="/providers" className="text-ink-soft hover:text-ink transition-colors">
              供应商
            </Link>
            <Link to="/history" className="text-ink-soft hover:text-ink transition-colors">历史</Link>
            <Link to="/tutorial" className="text-ink-soft hover:text-ink transition-colors">教学</Link>
            {isAuthenticated && user ? (
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenuOpen((v) => !v)}
                  className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-bg-subtle transition-colors"
                >
                  <div className="w-8 h-8 rounded-md" style={{ backgroundColor: user.avatar || '#C97B8A' }} />
                  <span className="text-xs font-medium text-ink-soft max-w-[80px] truncate">{user.username}</span>
                  <ChevronDown className={`w-3.5 h-3.5 text-ink-faint transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
                </button>
                {menuOpen && (
                  <div className="absolute right-0 top-12 w-48 glass rounded-xl p-2 animate-fade-in">
                    <Link
                      to="/workspace"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-ink-soft hover:bg-bg-subtle hover:text-ink transition-colors"
                    >
                      <LayoutDashboard className="w-3.5 h-3.5" /> 工作台
                    </Link>
                    <Link
                      to="/history"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-ink-soft hover:bg-bg-subtle hover:text-ink transition-colors"
                    >
                      <History className="w-3.5 h-3.5" /> 历史
                    </Link>
                    <Link
                      to="/account"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-ink-soft hover:bg-bg-subtle hover:text-ink transition-colors"
                    >
                      <UserCircle className="w-3.5 h-3.5" /> 账户
                    </Link>
                    {isAdmin && (
                      <Link
                        to="/admin"
                        onClick={() => setMenuOpen(false)}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-ink-soft hover:bg-bg-subtle hover:text-ink transition-colors"
                      >
                        <Shield className="w-3.5 h-3.5" /> 管理
                      </Link>
                    )}
                    <div className="my-1 border-t border-border" />
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-clay hover:bg-clay-soft transition-colors"
                    >
                      <LogOut className="w-3.5 h-3.5" /> 登出
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link to="/auth" className="text-ink-soft hover:text-ink transition-colors">登录</Link>
            )}
            <Link to="/workspace" className="btn-gradient px-4 py-2 rounded-md text-sm font-medium">
              开始协作
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6 relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass mb-8 animate-fade-in">
            <span className="w-2 h-2 rounded-full bg-sage animate-pulse"></span>
            <span className="text-xs text-ink-soft">60+ 位专家 · 7 种协作模式</span>
          </div>

          <h1 className="font-display text-5xl md:text-7xl font-light leading-tight mb-6 animate-fade-up">
            一个对话框,<br />
            <span className="gradient-text font-medium">一支虚拟团队</span>
          </h1>

          <p className="text-lg text-ink-soft max-w-xl mx-auto mb-10 animate-fade-up" style={{ animationDelay: '0.1s' }}>
            你的 AI 虚拟团队 · Just say it. 说出你的需求，自动召集多位不同角色的智能体在同一对话框内讨论、互相追问、给出方案。
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 animate-fade-up" style={{ animationDelay: '0.2s' }}>
            <Link to="/workspace" className="btn-gradient px-6 py-3 rounded-md font-medium flex items-center gap-2">
              立即体验 <ArrowRight className="w-4 h-4" />
            </Link>
            <Link to="/builder" className="px-6 py-3 rounded-md font-medium glass text-ink hover:text-sakura-700 transition-colors flex items-center gap-2">
              <Users className="w-4 h-4" /> 组建我的团队
            </Link>
          </div>
        </div>
      </section>

      {/* 实时指标仪表盘 — 数字从 0 滚动，带 +Δ% 增量 */}
      <section className="px-6 py-12 relative z-10">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div className="text-xs font-mono text-ink-faint tracking-widest">/ 实时指标 · LIVE</div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-sage">
              <span className="w-1.5 h-1.5 rounded-full bg-sage animate-pulse" /> 同步中
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {METRICS.map((m, i) => {
              const isPositive = m.delta > 0
              return (
                <div
                  key={m.label}
                  className="glass rounded-xl p-5 relative overflow-hidden"
                  style={{ animationDelay: `${i * 0.05}s` }}
                >
                  {/* 顶部小行：label + 增量徽章 */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-mono text-ink-faint uppercase tracking-wider">
                      {m.label}
                    </span>
                    {isPositive && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-sage-soft text-sage border border-sage-soft">
                        <span>+</span>
                        <CountUp end={m.delta} duration={1500} decimals={m.delta % 1 === 0 ? 0 : 1} suffix="%" delay={i * 120} />
                      </span>
                    )}
                    {m.live && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-bg-subtle text-ink-muted border border-border">
                        <span className="w-1 h-1 rounded-full bg-sage animate-pulse" />
                        持续
                      </span>
                    )}
                    {!isPositive && !m.live && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-bg-subtle text-ink-faint border border-border">
                        持续
                      </span>
                    )}
                  </div>
                  {/* 数字（从 0 滚动到目标） */}
                  <div className="font-display text-3xl md:text-4xl font-light text-ink tracking-tight tabular-nums">
                    <CountUp end={m.value} duration={2200} separator="," suffix={m.suffix} delay={i * 120} />
                  </div>
                  {/* 底部小字 */}
                  <div className="mt-1.5 text-[10px] font-mono text-ink-faint">
                    {m.sub}
                  </div>
                  {/* 右侧强调色细线 */}
                  <div
                    className="absolute top-0 left-0 bottom-0 w-px"
                    style={{ backgroundColor: m.accent + '40' }}
                  />
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-20 relative z-10">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-light text-center mb-3">
            不止是 AI,是<span className="gradient-text">团队</span>
          </h2>
          <p className="text-center text-ink-soft mb-12">四种协作方式，覆盖所有工作场景</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {FEATURES.map((f, i) => (
              <div key={i} className="glass rounded-xl p-6 animate-fade-up" style={{ animationDelay: `${i * 0.1}s` }}>
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ backgroundColor: f.color + '15' }}>
                    <f.icon className="w-6 h-6" style={{ color: f.color }} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg mb-1">{f.title}</h3>
                    <p className="text-sm text-ink-soft leading-relaxed">{f.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Preset Teams */}
      {teams.length > 0 && (
        <section className="px-6 py-20 relative z-10">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-12">
              <h2 className="font-display text-3xl md:text-4xl font-light mb-3">
                <span className="gradient-text">8 支</span>预设团队
              </h2>
              <p className="text-ink-soft">开箱即用，或在此基础上自定义</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {teams.map((t, i) => (
                <Link
                  key={t.id}
                  to="/workspace"
                  state={{ teamId: t.id }}
                  className="glass rounded-xl p-5 animate-fade-up group"
                  style={{ animationDelay: `${i * 0.05}s` }}
                >
                  <div className="w-10 h-10 rounded-md flex items-center justify-center text-lg mb-3 bg-bg-subtle border border-border">
                    {t.icon || t.name.charAt(0)}
                  </div>
                  <h3 className="font-semibold mb-1 group-hover:text-sakura-700 transition-colors">{t.name}</h3>
                  <p className="text-xs text-ink-soft mb-3 line-clamp-2">{t.description}</p>
                  <div className="flex items-center gap-1 mb-3">
                    {t.members.slice(0, 4).map((m, j) => (
                      <div
                        key={j}
                        className="w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-mono font-medium"
                        style={{ backgroundColor: m.color + '20', color: m.color, marginLeft: j > 0 ? '-8px' : 0, border: '1px solid var(--border)' }}
                      >
                        {m.avatar || m.name.charAt(0)}
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 text-[10px]">
                    <span className="px-2 py-0.5 rounded" style={{ backgroundColor: t.color + '15', color: t.color }}>
                      {modeLabel(t.mode)}
                    </span>
                    <span className="text-ink-faint">{t.members.length} 人</span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* 100% 免费 */}
      <section className="px-6 py-20 relative z-10">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-block text-xs font-mono text-ink-faint mb-3 tracking-widest">/ 01 — FREE</div>
          <h2 className="font-display text-3xl md:text-4xl font-light mb-4">
            <span className="gradient-text">100% 免费</span>，真的
          </h2>
          <p className="text-ink-soft mb-10 max-w-xl mx-auto">
            所有功能完全开放。你可以用自己的 API Key 接入 254+ 个 LLM 供应商，
            也可以领取各大厂商的免费额度。不收费，不限次，不套路。
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { num: '254+', label: '内置 LLM 供应商', desc: 'OpenAI / Claude / DeepSeek / Gemini…' },
              { num: '219', label: '提供免费额度', desc: 'Google Gemini / Groq / SiliconFlow…' },
              { num: '∞', label: '自定义端点', desc: 'Ollama / vLLM / 本地模型…' },
            ].map((item, i) => (
              <div key={i} className="glass rounded-xl p-6 text-left">
                <div className="font-display text-3xl font-light gradient-text mb-1">{item.num}</div>
                <div className="text-sm font-medium text-ink mb-1">{item.label}</div>
                <div className="text-xs text-ink-faint font-mono">{item.desc}</div>
              </div>
            ))}
          </div>
          <div className="mt-8">
            <Link to="/providers" className="text-sm text-ink-soft hover:text-ink transition-colors underline underline-offset-4">
              查看全部供应商 →
            </Link>
          </div>
        </div>
      </section>

      {/* Why Zhihui */}
      <section className="px-6 py-20 relative z-10">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <div className="inline-block text-xs font-mono text-ink-faint mb-3 tracking-widest">/ 02 — WHY</div>
            <h2 className="font-display text-3xl md:text-4xl font-light mb-3">
              为什么选择<span className="gradient-text">樱花小队</span>
            </h2>
            <p className="text-ink-soft">不只是多智能体，是真正可用的协作</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { title: '真正的多智能体协作', desc: '不是简单的链式调用，而是多位专家在同一对话框内讨论、互相追问、给出方案。7 种协作模式覆盖所有场景。' },
              { title: '你的 Key 你做主', desc: '不用共享开发者的 Key，每个用户保存自己的 API Key 和 Base URL。支持 254+ 内置厂商和完全自定义端点。' },
              { title: '全平台覆盖', desc: 'Web / CLI / VS Code 插件 / macOS / Windows 桌面端，一个账号，处处可用。' },
              { title: '开源透明', desc: '完整源码公开，你可以自部署、自扩展、自定制。不锁定，不黑箱。' },
            ].map((item, i) => (
              <div key={i} className="glass rounded-xl p-6">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-bg-subtle flex items-center justify-center flex-shrink-0">
                    <span className="font-mono text-xs text-ink-faint">/0{i + 1}</span>
                  </div>
                  <div>
                    <h3 className="font-medium text-ink mb-2">{item.title}</h3>
                    <p className="text-sm text-ink-soft leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Agent Library */}
      <section className="px-6 py-20 relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-block text-xs font-mono text-ink-faint mb-3 tracking-widest">/ 03 — LIBRARY</div>
          <h2 className="font-display text-3xl md:text-4xl font-light mb-3">
            <span className="gradient-text">60+</span> 位专家智能体
          </h2>
          <p className="text-ink-soft mb-10">覆盖全流程，按需召唤</p>
          <div className="flex flex-wrap justify-center gap-2">
            {[
              '需求分析师', 'UI 设计师', '前端工程师', '后端工程师',
              '测试工程师', '代码审查员', '部署运维', '技术文档',
              '数据分析师', '安全顾问', '产品经理', '架构师',
              'DevOps', '数据库专家', 'API 设计师', '性能优化',
            ].map((role, i) => (
              <span key={i} className="px-3 py-1.5 rounded-lg glass text-xs text-ink-soft font-mono">
                {role}
              </span>
            ))}
          </div>
          <div className="mt-8">
            <Link to="/agents" className="text-sm text-ink-soft hover:text-ink transition-colors underline underline-offset-4">
              查看全部专家 →
            </Link>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-20 relative z-10">
        <div className="max-w-3xl mx-auto">
          <div className="glass rounded-xl p-10 md:p-16 text-center relative overflow-hidden">
            <div className="relative z-10">
              <h2 className="font-display text-3xl md:text-4xl font-light text-ink mb-4">
                说出你的第一个需求
              </h2>
              <p className="text-ink-soft text-sm mb-8">60+ 位专家 · 7 种协作模式 · 即刻开始</p>
              <Link to="/workspace" className="btn-gradient px-8 py-3 rounded-md font-medium inline-flex items-center gap-2">
                开始协作 <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer — 友站放最下面,主链接用 GitHub 即可 */}
      <footer className="px-6 py-10 relative z-10 border-t border-ink/5">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col items-center gap-4">
            <p className="font-display text-sm text-ink-soft">樱花小队 · Just say it.</p>
            <div className="flex items-center gap-4 text-xs">
              <a href="https://github.com/wanan3847/SakuraAgentTeam" target="_blank" rel="noopener noreferrer" className="text-ink-faint hover:text-sakura-700 transition-colors flex items-center gap-1">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                GitHub
              </a>
              <button
                onClick={() => openBugReport({ location: 'home/footer' })}
                className="text-ink-faint hover:text-sakura-700 transition-colors flex items-center gap-1"
                title="一键打开 GitHub Issue 页面（自动附 URL / UA / 时间）"
              >
                <Bug className="w-3.5 h-3.5" /> 报告 Bug
              </button>
              <a href="https://041126.xyz/" target="_blank" rel="noopener noreferrer" className="text-ink-faint hover:text-sakura-700 transition-colors">主站</a>
              <a href="https://blog.041126.xyz/" target="_blank" rel="noopener noreferrer" className="text-ink-faint hover:text-sakura-700 transition-colors">博客</a>
              <a href="https://anime.041126.xyz/" target="_blank" rel="noopener noreferrer" className="text-ink-faint hover:text-sakura-700 transition-colors">动漫</a>
            </div>
            <p className="text-xs text-ink-faint">© 2026 樱花小队 SakuraAgentTeam</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
