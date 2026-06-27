import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Search, ArrowLeft, Plus, Loader2, Users, Target, BookOpen, Zap, User, Sprout, X } from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import { fetchAgents, fetchCategories, AgentInfo, Category } from '../lib/teamApi'
import { fetchPublicSubmissions, AgentSubmission } from '../lib/submissionApi'

const CATEGORY_COLORS: Record<string, string> = {
  creative: '#C97B8A', design: '#8C4A57', tech: '#6B655C',
  research: '#C4955E', strategy: '#6B655C', qa: '#B56B6B', industry: '#6B8E6B',
  education: '#C97B8A', finance: '#6B655C', legal: '#8C4A57',
  healthcare: '#6B8E6B', media: '#B56B6B', music: '#9A5A68',
  writing: '#6B655C', data: '#4A4540', devops: '#C4955E',
  business: '#6B8E6B',
}

export default function AgentLibraryPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [activeCat, setActiveCat] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [detailAgent, setDetailAgent] = useState<AgentInfo | null>(null)
  const [tab, setTab] = useState<'library' | 'community'>('library')
  const [communityAgents, setCommunityAgents] = useState<AgentSubmission[]>([])
  const [communityLoading, setCommunityLoading] = useState(false)
  const [communityError, setCommunityError] = useState('')

  useEffect(() => {
    fetchAgents().then((d) => setAgents(d?.agents || [])).catch(() => {})
    fetchCategories().then((d) => setCategories(d || [])).catch(() => {})
  }, [])

  const loadCommunity = async () => {
    setCommunityLoading(true)
    setCommunityError('')
    try {
      const data = await fetchPublicSubmissions()
      setCommunityAgents(data || [])
    } catch (e: any) {
      setCommunityError(e.message || '加载失败')
    } finally {
      setCommunityLoading(false)
    }
  }

  useEffect(() => {
    if (tab === 'community' && communityAgents.length === 0 && !communityLoading) {
      loadCommunity()
    }
  }, [tab])

  const filtered = agents.filter((a) => {
    if (activeCat !== 'all' && a.category !== activeCat) return false
    if (search) {
      const q = search.toLowerCase()
      return a.name.toLowerCase().includes(q) || a.tagline.toLowerCase().includes(q) || a.skills.some((s) => s.toLowerCase().includes(q))
    }
    return true
  })

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="aurora-bg min-h-screen relative">
      <SakuraPetals count={4} />

      {/* 顶栏 */}
      <nav className="sticky top-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-soft hover:text-ink transition-colors">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回</span>
          </Link>
          <h1 className="font-medium text-lg text-ink">专家库</h1>
          {selected.size > 0 ? (
            <Link
              to="/builder"
              state={{ preselected: Array.from(selected) }}
              className="btn-gradient px-4 py-2 rounded-md text-sm font-medium flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> 组建团队 ({selected.size})
            </Link>
          ) : (
            <Link to="/builder" className="text-sm text-ink-soft hover:text-ink transition-colors">组建团队 →</Link>
          )}
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8 relative z-10">
        {/* Tab 切换 */}
        <div className="flex p-1 bg-bg-subtle rounded-full mb-6 max-w-md">
          <button
            onClick={() => setTab('library')}
            className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${tab === 'library' ? 'btn-gradient' : 'text-ink-soft hover:text-ink'}`}
          >
            专家库 ({agents.length})
          </button>
          <button
            onClick={() => setTab('community')}
            className={`flex-1 py-2 rounded-full text-sm font-medium transition-all flex items-center justify-center gap-1.5 ${tab === 'community' ? 'btn-gradient' : 'text-ink-soft hover:text-ink'}`}
          >
            <Users className="w-3.5 h-3.5" /> 社区贡献 ({communityAgents.length})
          </button>
        </div>

        {tab === 'library' ? (
          <>
        {/* 搜索 */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
            <input
              name="agent-library-search"
              id="agent-library-search"
              autoComplete="off"
              data-form-type="other"
              spellCheck={false}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索 60+ 位专家..."
              className="w-full glass rounded-md pl-11 pr-4 py-3 text-sm border border-border focus:border-ink-muted outline-none"
            />
          </div>
        </div>

        {/* 分类标签 */}
        <div className="flex flex-wrap gap-2 mb-8">
          <button
            onClick={() => setActiveCat('all')}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${activeCat === 'all' ? 'btn-gradient' : 'glass text-ink-soft hover:text-ink'}`}
          >
            全部 ({agents.length})
          </button>
          {(categories || []).map((c) => {
            const count = agents.filter((a) => a.category === c.id).length
            const isActive = activeCat === c.id
            const color = CATEGORY_COLORS[c.id] || '#A8A299'
            return (
              <button
                key={c.id}
                onClick={() => setActiveCat(c.id)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${isActive ? 'text-surface' : 'glass text-ink-soft hover:text-ink'}`}
                style={isActive ? { backgroundColor: color } : {}}
              >
                {c.name} ({count})
              </button>
            )
          })}
        </div>

        {/* 借鉴成熟框架 — 让用户知道不是自造 */}
        <details className="mb-8 group">
          <summary className="cursor-pointer text-xs font-mono text-ink-faint tracking-widest hover:text-ink-muted select-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition-transform">▸</span>
            / 关于这些 Agent 的设计来源
          </summary>
          <div className="mt-3 p-4 rounded-xl border border-border bg-bg-subtle">
            <p className="text-sm text-ink-soft leading-relaxed mb-3">
              100 位专家的设计借鉴了业界 <strong>成熟的多智能体框架</strong>，不是项目自己造的概念：
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              {[
                { name: 'CrewAI',   use: 'role / goal / backstory / skills 四件套 + ProcessType 6 种执行模式' },
                { name: 'AG2 (AutoGen)', use: 'GroupChat 群聊 + Manager 决定发言者 + SpeakerMode 3 种' },
                { name: 'Anthropic Orchestrator-Workers', use: '并行子任务调度 + 共享白板产物链' },
                { name: 'MetaGPT',  use: 'ProductManager / Architect / Engineer 流水线 + SOP 化产物' },
                { name: 'OpenAI Swarm', use: 'Handoff 模式：agent 之间能互相转交任务' },
                { name: 'LangGraph', use: '任务状态机 + DAG 依赖 + 检查点持久化' },
              ].map((f) => (
                <div key={f.name} className="rounded border border-border bg-surface px-3 py-2">
                  <div className="font-medium text-ink">{f.name}</div>
                  <div className="text-ink-muted mt-0.5 font-mono text-[11px] leading-relaxed">{f.use}</div>
                </div>
              ))}
            </div>
            <p className="text-xs text-ink-muted mt-3 leading-relaxed">
              你也可以点「创建 Agent」自建专家（系统会自动从 LLM 推导出 role/goal/skills），提交后经过审核可以进入社区。
            </p>
          </div>
        </details>

        {/* Agent 网格 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {(filtered || []).map((a, i) => {
            const isSelected = selected.has(a.id)
            const color = CATEGORY_COLORS[a.category] || '#A8A299'
            return (
              <div
                key={a.id}
                onClick={() => toggleSelect(a.id)}
                className={`glass rounded-2xl p-5 cursor-pointer animate-fade-up transition-all ${isSelected ? 'selected-ring' : ''}`}
                style={{ animationDelay: `${i * 0.03}s` }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="w-12 h-12 rounded-md flex items-center justify-center text-2xl bg-bg-subtle border border-border">
                    {a.avatar}
                  </div>
                  {isSelected && (
                    <div className="w-6 h-6 rounded-full bg-sakura-400 flex items-center justify-center">
                      <svg className="w-3.5 h-3.5 text-surface" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>
                <h3 className="font-semibold text-base mb-0.5">{a.name}</h3>
                <p className="text-xs text-ink-faint mb-2 font-mono">{a.role}</p>
                <p className="text-sm text-ink-soft leading-relaxed mb-3">{a.tagline}</p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {a.skills.slice(0, 3).map((s, j) => (
                    <span key={j} className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: color + '10', color }}>
                      {s}
                    </span>
                  ))}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setDetailAgent(a) }}
                  className="w-full text-xs py-1.5 rounded-full glass text-ink-soft hover:text-sakura-700 transition-colors flex items-center justify-center gap-1"
                >
                  查看详情 →
                </button>
              </div>
            )
          })}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-20">
            <div className="w-12 h-12 mx-auto mb-3 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
              <Search className="w-5 h-5 text-ink-faint" />
            </div>
            <p className="text-ink-soft">没有找到匹配的专家</p>
          </div>
        )}
          </>
        ) : (
          /* 社区贡献 Tab */
          <div>
            {communityError && (
              <div className="mb-4 text-xs text-clay bg-clay-soft border border-clay-soft rounded-lg px-3 py-2">
                {communityError}
              </div>
            )}

            {communityLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="w-6 h-6 animate-spin text-ink-muted" />
              </div>
            ) : communityAgents.length === 0 ? (
              <div className="text-center py-20 animate-fade-in">
                <div className="w-12 h-12 mx-auto mb-3 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
                  <Sprout className="w-5 h-5 text-ink-faint" />
                </div>
                <p className="text-sm text-ink-soft mb-2">还没有社区贡献</p>
                <p className="text-xs text-ink-faint mb-6">成为第一个贡献者，分享你的 Agent</p>
                <Link to="/tutorial" className="btn-gradient inline-flex items-center gap-2 px-5 py-2 rounded-md text-xs font-medium">
                  <Plus className="w-3.5 h-3.5" /> 创建 Agent
                </Link>
              </div>
            ) : (
              <>
                {/* 社区贡献说明 */}
                <div className="mb-6 glass rounded-xl p-4 flex items-start gap-2 text-xs text-ink-soft">
                  <Users className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-ink-muted" />
                  <div className="leading-relaxed">
                    以下 Agent 由社区用户贡献并经管理员审核通过。点击卡片查看详情，可加入你的团队组建。
                  </div>
                </div>

                {/* 社区 Agent 网格 */}
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {(communityAgents || []).map((item, i) => {
                    const color = item.agent_color || CATEGORY_COLORS[item.agent_category] || '#8C4A57'
                    return (
                      <div
                        key={item.id}
                        onClick={() => toggleSelect(item.agent_id)}
                        className={`glass rounded-2xl p-5 cursor-pointer animate-fade-up transition-all relative ${selected.has(item.agent_id) ? 'selected-ring' : ''}`}
                        style={{ animationDelay: `${i * 0.03}s` }}
                      >
                        {/* 社区贡献徽章 */}
                        <div className="absolute -top-2 -right-2 px-2 py-0.5 rounded-full text-[9px] font-medium bg-sakura-400 text-surface shadow-sm flex items-center gap-0.5">
                          社区贡献
                        </div>

                        <div className="flex items-start justify-between mb-3">
                          <div className="w-12 h-12 rounded-md flex items-center justify-center text-2xl bg-bg-subtle border border-border">
                            {item.agent_avatar || item.agent_name.charAt(0).toUpperCase()}
                          </div>
                          {selected.has(item.agent_id) && (
                            <div className="w-6 h-6 rounded-full bg-sakura-400 flex items-center justify-center">
                              <svg className="w-3.5 h-3.5 text-surface" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                            </div>
                          )}
                        </div>
                        <h3 className="font-semibold text-base mb-0.5">{item.agent_name}</h3>
                        <p className="text-xs text-ink-faint mb-2 font-mono">{item.agent_role}</p>
                        <p className="text-sm text-ink-soft leading-relaxed mb-3 line-clamp-2">{item.agent_tagline}</p>
                        <div className="flex flex-wrap gap-1 mb-3">
                          {(item.agent_skills || []).slice(0, 3).map((s, j) => (
                            <span key={j} className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: color + '10', color }}>
                              {s}
                            </span>
                          ))}
                        </div>
                        {/* 贡献者 */}
                        <div className="flex items-center gap-1.5 text-[10px] text-ink-faint pt-2 border-t border-border">
                          <div className="w-4 h-4 rounded-full bg-surface-hover flex items-center justify-center"><User className="w-3 h-3" /></div>
                          <span>由 <span className="font-medium text-ink-soft">{item.username}</span> 贡献</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* 详情弹窗 */}
      {detailAgent && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-ink/40 animate-fade-in"
          onClick={() => setDetailAgent(null)}
        >
          <div
            className="glass rounded-xl p-8 max-w-lg w-full max-h-[85vh] overflow-y-auto relative"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setDetailAgent(null)}
              aria-label="关闭"
              className="absolute top-4 right-4 w-8 h-8 rounded-md glass flex items-center justify-center text-ink-faint hover:text-ink hover:border-ink-muted transition-colors"
            >
              <X className="w-4 h-4" strokeWidth={1.5} />
            </button>
            <div className="flex items-center gap-4 mb-5">
              <div className="w-16 h-16 rounded-md flex items-center justify-center text-3xl flex-shrink-0 bg-bg-subtle border border-border">
                {detailAgent.avatar}
              </div>
              <div>
                <h2 className="font-display text-2xl text-ink">{detailAgent.name}</h2>
                <p className="text-xs text-ink-faint font-mono">{detailAgent.role}</p>
              </div>
            </div>
            <p className="text-sm text-ink-soft leading-relaxed mb-5">{detailAgent.tagline}</p>

            {detailAgent.goal && (
              <div className="mb-4">
                <h3 className="text-xs font-semibold text-ink-faint uppercase tracking-wider mb-2 flex items-center gap-1"><Target className="w-3 h-3" /> 目标</h3>
                <p className="text-sm text-ink-soft leading-relaxed glass rounded-xl p-3">{detailAgent.goal}</p>
              </div>
            )}

            {detailAgent.backstory && (
              <div className="mb-4">
                <h3 className="text-xs font-semibold text-ink-faint uppercase tracking-wider mb-2 flex items-center gap-1"><BookOpen className="w-3 h-3" /> 背景</h3>
                <p className="text-sm text-ink-soft leading-relaxed glass rounded-xl p-3">{detailAgent.backstory}</p>
              </div>
            )}

            <div className="mb-5">
              <h3 className="text-xs font-semibold text-ink-faint uppercase tracking-wider mb-2 flex items-center gap-1"><Zap className="w-3 h-3" /> 技能</h3>
              <div className="flex flex-wrap gap-1.5">
                {(detailAgent.skills || []).map((s, j) => (
                  <span
                    key={j}
                    className="text-xs px-2.5 py-1 rounded-full"
                    style={{ backgroundColor: (CATEGORY_COLORS[detailAgent.category] || '#A8A299') + '15', color: CATEGORY_COLORS[detailAgent.category] || '#A8A299' }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>

            <button
              onClick={() => { toggleSelect(detailAgent.id); setDetailAgent(null) }}
              className="btn-gradient w-full py-2.5 rounded-md text-sm font-medium"
            >
              {selected.has(detailAgent.id) ? '✓ 已选入团队' : '+ 加入团队组建'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
