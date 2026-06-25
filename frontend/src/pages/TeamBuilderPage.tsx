import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Search, X, Users, Workflow, Bot, ArrowRight, Check, GitBranch, Repeat, Network } from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import { fetchAgents, fetchCategories, AgentInfo, Category } from '../lib/teamApi'

const CATEGORY_COLORS: Record<string, string> = {
  creative: '#C97B8A', design: '#8C4A57', tech: '#6B655C',
  research: '#C4955E', strategy: '#6B655C', qa: '#B56B6B', industry: '#6B8E6B',
  education: '#C97B8A', finance: '#6B655C', legal: '#8C4A57',
  healthcare: '#6B8E6B', media: '#B56B6B', music: '#9A5A68',
  writing: '#6B655C', data: '#4A4540', devops: '#C4955E',
  business: '#6B8E6B',
}

// 借鉴业界 7 种协作模式（CrewAI / AG2 / Anthropic / MetaGPT / OpenAI Swarm / LangGraph）
const MODES = [
  { id: 'group', name: '群聊模式', icon: Users, desc: '成员依次发言，能看到彼此，适合讨论', color: '#C97B8A' },
  { id: 'pipeline', name: '流水线模式', icon: Workflow, desc: '按顺序接力，基于上一个产出，适合生产', color: '#8C4A57' },
  { id: 'master', name: '管家模式', icon: Bot, desc: '主管分析任务，召唤成员，借鉴 CrewAI Hierarchical', color: '#6B655C' },
  { id: 'consensus', name: '共识模式', icon: Network, desc: '每个成员都发言，最后达成共识，借鉴 AG2 GroupChat', color: '#C4955E' },
  { id: 'parallel', name: '并行模式', icon: Repeat, desc: '多个成员同时工作，借鉴 Anthropic Orchestrator-Workers', color: '#6B8E6B' },
  { id: 'handoff', name: '转交模式', icon: ArrowRight, desc: '成员之间能互相转交任务，借鉴 OpenAI Swarm', color: '#6B8E6B' },
  { id: 'graph', name: '状态图模式', icon: GitBranch, desc: '任务组成 DAG 节点，依赖并行执行，借鉴 LangGraph', color: '#9A5A68' },
]

export default function TeamBuilderPage() {
  const location = useLocation()
  const nav = useNavigate()
  const preselected = (location.state as any)?.preselected as string[] | undefined

  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set(preselected || []))
  const [search, setSearch] = useState('')
  const [activeCat, setActiveCat] = useState('all')
  const [teamName, setTeamName] = useState('')
  const [mode, setMode] = useState('group')

  useEffect(() => {
    fetchAgents().then((d) => setAgents(d.agents)).catch(() => {})
    fetchCategories().then(setCategories).catch(() => {})
  }, [])

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < 6) next.add(id) // 最多 6 人
      return next
    })
  }

  const selectedAgents = agents.filter((a) => selected.has(a.id))
  const filtered = agents.filter((a) => {
    if (activeCat !== 'all' && a.category !== activeCat) return false
    if (search) {
      const q = search.toLowerCase()
      return a.name.toLowerCase().includes(q) || a.tagline.toLowerCase().includes(q)
    }
    return true
  })

  const handleLaunch = () => {
    if (selected.size < 2) return
    nav('/workspace', {
      state: {
        adhocTeam: {
          name: teamName || '我的团队',
          member_ids: Array.from(selected),
          mode,
        },
      },
    })
  }

  return (
    <div className="aurora-bg min-h-screen relative">
      <SakuraPetals count={3} />

      {/* 顶栏 */}
      <nav className="sticky top-0 z-50 glass">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-soft hover:text-ink transition-colors">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回</span>
          </Link>
          <h1 className="font-medium text-lg text-ink">组建团队</h1>
          <div className="w-16"></div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：选人区 */}
          <div className="lg:col-span-2">
            {/* 搜索 */}
            <div className="relative mb-4">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
              <input
                name="expert-search"
                id="expert-search"
                autoComplete="off"
                data-form-type="other"
                spellCheck={false}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索专家..."
                className="w-full glass rounded-md pl-11 pr-4 py-2.5 text-sm border border-border focus:border-ink-muted outline-none"
              />
            </div>

            {/* 分类 */}
            <div className="flex flex-wrap gap-2 mb-4">
              <button
                onClick={() => setActiveCat('all')}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${activeCat === 'all' ? 'btn-gradient' : 'glass text-ink-soft'}`}
              >
                全部
              </button>
              {categories.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveCat(c.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${activeCat === c.id ? 'text-surface' : 'glass text-ink-soft'}`}
                  style={activeCat === c.id ? { backgroundColor: CATEGORY_COLORS[c.id] } : {}}
                >
                  {c.name}
                </button>
              ))}
            </div>

            {/* Agent 网格 */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto pr-2">
              {filtered.map((a) => {
                const isSelected = selected.has(a.id)
                const color = CATEGORY_COLORS[a.category] || '#A8A299'
                return (
                  <div
                    key={a.id}
                    onClick={() => toggleSelect(a.id)}
                    className={`glass rounded-xl p-3 cursor-pointer transition-all ${isSelected ? 'selected-ring' : ''}`}
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="w-10 h-10 rounded-md flex items-center justify-center text-xl flex-shrink-0 bg-bg-subtle border border-border">
                        {a.avatar}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-sm truncate">{a.name}</div>
                        <div className="text-[10px] text-ink-faint truncate">{a.tagline}</div>
                      </div>
                      {isSelected && (
                        <div className="w-5 h-5 rounded-full bg-sakura-400 flex items-center justify-center flex-shrink-0">
                          <Check className="w-3 h-3 text-surface" />
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 右侧：团队配置 */}
          <div className="lg:sticky lg:top-24 h-fit">
            <div className="glass rounded-2xl p-6">
              <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                我的团队
              </h3>

              {/* 团队名 */}
              <input
                name="team-name"
                id="team-name"
                autoComplete="off"
                data-form-type="other"
                spellCheck={false}
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                placeholder="给团队起个名字..."
                className="w-full bg-surface rounded-md px-4 py-2.5 text-sm border border-border focus:border-ink-muted outline-none mb-4"
              />

              {/* 模式选择 */}
              <div className="mb-4">
                <div className="text-xs text-ink-faint mb-2 font-medium">协作模式</div>
                <div className="space-y-2">
                  {MODES.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setMode(m.id)}
                      className={`w-full text-left p-3 rounded-xl transition-all flex items-start gap-2.5 ${mode === m.id ? 'selected-ring bg-surface-hover border border-border' : 'bg-bg-subtle hover:bg-surface-hover border border-border'}`}
                    >
                      <m.icon className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: m.color }} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium">{m.name}</div>
                        <div className="text-[10px] text-ink-soft leading-relaxed">{m.desc}</div>
                      </div>
                      {mode === m.id && <Check className="w-4 h-4 text-sakura-400 flex-shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* 已选成员 */}
              <div className="mb-4">
                <div className="text-xs text-ink-faint mb-2 font-medium">
                  成员 ({selected.size}/6)
                </div>
                {selectedAgents.length === 0 ? (
                  <div className="text-center py-6 text-xs text-ink-faint">
                    从左侧选择专家加入团队
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedAgents.map((a, i) => {
                      const color = CATEGORY_COLORS[a.category] || '#A8A299'
                      return (
                        <div key={a.id} className="flex items-center gap-2 bg-bg-subtle rounded-md p-2 border border-border">
                          <span className="text-[10px] font-mono text-ink-faint w-4">{i + 1}</span>
                          <div className="w-7 h-7 rounded-md flex items-center justify-center text-sm bg-bg-subtle border border-border">
                            {a.avatar}
                          </div>
                          <span className="text-sm font-medium flex-1">{a.name}</span>
                          <button onClick={() => toggleSelect(a.id)} className="text-ink-faint hover:text-clay transition-colors">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* 启动按钮 */}
              <button
                onClick={handleLaunch}
                disabled={selected.size < 2}
                className="w-full btn-gradient rounded-xl py-3 font-medium flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                启动团队 <ArrowRight className="w-4 h-4" />
              </button>
              {selected.size < 2 && (
                <p className="text-center text-[10px] text-ink-faint mt-2">至少选择 2 位专家</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
