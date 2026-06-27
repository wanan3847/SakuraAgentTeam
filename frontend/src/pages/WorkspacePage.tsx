import { useState, useRef, useEffect, useCallback } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Send, Trash2, Download, Loader2, ChevronDown, ChevronRight,
  GitBranch, Network, Repeat, Bot, Users, Workflow, ArrowRight,
  Activity, Eye, FileText, MessageSquare, AlertCircle, MapPin,
  Wrench, Upload, Clock, X,
} from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import {
  fetchTeams, streamTeamChat, exportChat, fetchWhiteboard,
  fetchCollaborationState, fetchCollaborationArtifacts, fetchFinalDeliverable,
  TeamInfo, ChatMessage, AgentTraceData, GraphSnapshot, WhiteboardData, TeamMode,
  CollabArtifact, CollaborationState,
} from '../lib/teamApi'
import {
  Award, BookOpen, Layers,
} from 'lucide-react'

// 7 种模式（借鉴 CrewAI / AG2 / Anthropic / OpenAI Swarm / LangGraph / MetaGPT）
const MODE_LABELS: Record<TeamMode, { name: string; icon: any; color: string }> = {
  group: { name: '群聊模式', icon: Users, color: '#C97B8A' },
  pipeline: { name: '流水线模式', icon: Workflow, color: '#8C4A57' },
  master: { name: '管家模式', icon: Bot, color: '#6B655C' },
  consensus: { name: '共识模式', icon: Network, color: '#C4955E' },
  parallel: { name: '并行模式', icon: Repeat, color: '#6B8E6B' },
  handoff: { name: '转交模式', icon: ArrowRight, color: '#6B8E6B' },
  graph: { name: '状态图模式', icon: GitBranch, color: '#9A5A68' },
}

// 任务状态颜色
const TASK_STATE_COLORS: Record<string, string> = {
  pending: '#A8A299', ready: '#C4955E', running: '#6B655C',
  done: '#6B8E6B', failed: '#B56B6B', skipped: '#A8A299',
}

export default function WorkspacePage() {
  const location = useLocation()
  const nav = useNavigate()
  const initialState = location.state as any

  const [teams, setTeams] = useState<TeamInfo[]>([])
  const [activeTeam, setActiveTeam] = useState<TeamInfo | null>(null)
  const [adhocTeam, setAdhocTeam] = useState<{ name: string; member_ids: string[]; mode: TeamMode; icon?: string; color?: string } | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [thinkingAgent, setThinkingAgent] = useState<any>(null)

  // 状态图 / 白板 / trace 面板
  const [graphSnapshot, setGraphSnapshot] = useState<GraphSnapshot | null>(null)
  const [whiteboard, setWhiteboard] = useState<WhiteboardData | null>(null)
  const [traces, setTraces] = useState<Record<string, AgentTraceData>>({})  // agent_id -> trace
  const [handoffChain, setHandoffChain] = useState<string[]>([])

  // 新:协作产物 / 最终交付 / 会话状态
  const [collabSessionId, setCollabSessionId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<CollabArtifact[]>([])
  const [finalDeliverable, setFinalDeliverable] = useState<CollabArtifact | null>(null)
  const [showFinalDeliverable, setShowFinalDeliverable] = useState(false)
  const [showArtifacts, setShowArtifacts] = useState(false)

  // 面板显示
  const [showTeamPicker, setShowTeamPicker] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [showGraphPanel, setShowGraphPanel] = useState(true)
  const [showWhiteboard, setShowWhiteboard] = useState(false)
  const [showTraces, setShowTraces] = useState(false)
  const [expandedTrace, setExpandedTrace] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    fetchTeams().then((d) => {
      setTeams(d || [])
      if (initialState?.teamId) {
        const t = d.find((t) => t.id === initialState.teamId)
        if (t) setActiveTeam(t)
      }
      if (initialState?.adhocTeam) {
        setAdhocTeam(initialState.adhocTeam)
      }
      if (!initialState?.teamId && !initialState?.adhocTeam && d.length > 0) {
        setActiveTeam(d[0])
      }
    }).catch(() => {})
  }, [])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])
  useEffect(() => { scrollToBottom() }, [messages, thinkingAgent, scrollToBottom])

  useEffect(() => {
    const el = inputRef.current
    if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 160) + 'px' }
  }, [input])

  const currentTeamName = activeTeam?.name || adhocTeam?.name || '未选择团队'
  const currentMode: TeamMode = (activeTeam?.mode || adhocTeam?.mode || 'group') as TeamMode
  const modeMeta = MODE_LABELS[currentMode] || MODE_LABELS.group
  const currentMembers = activeTeam?.members || []
  const currentSessionId = activeTeam?.id || adhocTeam?.name || 'default'

  const handleSend = async (text?: string) => {
    const content = (text ?? input).trim()
    if (!content || isStreaming) return
    if (!activeTeam && !adhocTeam) return

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`, role: 'user', name: '我', content,
      avatar: '我', color: '#6B655C',
    }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setIsStreaming(true)

    // 清空面板
    setGraphSnapshot(null)
    setTraces({})
    setHandoffChain([])
    setWhiteboard(null)
    setCollabSessionId(null)
    setArtifacts([])
    setFinalDeliverable(null)
    setShowFinalDeliverable(false)
    setShowArtifacts(false)

    try {
      let currentAgentMsg: ChatMessage | null = null

      for await (const evt of streamTeamChat({
        teamId: activeTeam?.id || null,
        message: content,
        history: newMessages,
        adhocTeam: adhocTeam || undefined,
        max_handoffs: 5,
      })) {
        // === 新事件处理 ===

        if (evt.type === 'phase_start') {
          // 添加阶段标记消息
          setMessages((prev) => [...prev, {
            id: `phase-${Date.now()}-${Math.random()}`,
            role: 'phase', name: '阶段', avatar: '',
            color: '#8C4A57', content: '', stage: JSON.stringify(evt.data),
          }])
        }

        else if (evt.type === 'graph_snapshot') {
          setGraphSnapshot(evt.data as GraphSnapshot)
        }

        // ===== 新:协作产物 / 最终交付事件 =====
        else if (evt.type === 'task_plan_created') {
          // 任务计划创建 — 记录 session_id
          if (evt.data?.session_id) {
            setCollabSessionId(evt.data.session_id)
          }
          // 同时更新 graphSnapshot(如果有 tasks)
          if (evt.data?.tasks) {
            setGraphSnapshot({
              tasks: evt.data.tasks.map((t: any) => ({
                id: t.id, name: t.name, description: t.description,
                agent_id: t.agent_id, state: t.state,
                dependencies: t.dependencies,
                output_preview: t.expected_output,
              })),
              is_finished: false,
            })
          }
        }

        else if (evt.type === 'task_started') {
          // 任务开始 — 更新 graph 任务状态
          const d = evt.data
          setGraphSnapshot((prev) => {
            if (!prev) return prev
            return {
              ...prev,
              tasks: prev.tasks.map((t) =>
                t.id === d.task_id ? { ...t, state: 'running' as const } : t
              ),
            }
          })
        }

        else if (evt.type === 'task_completed') {
          // 任务完成 — 更新 graph 任务状态
          const d = evt.data
          setGraphSnapshot((prev) => {
            if (!prev) return prev
            return {
              ...prev,
              tasks: prev.tasks.map((t) =>
                t.id === d.task_id ? { ...t, state: d.state as any } : t
              ),
            }
          })
        }

        else if (evt.type === 'artifact_created') {
          // 产物创建 — 加入 artifacts 列表
          const artifact = evt.data?.artifact
          if (artifact) {
            setArtifacts((prev) => {
              // 避免重复
              if (prev.find((a) => a.id === artifact.id)) return prev
              return [...prev, artifact]
            })
            // 如果是最终产物,设置 finalDeliverable
            if (evt.data?.is_final) {
              setFinalDeliverable(artifact)
              setShowFinalDeliverable(true)
            }
          }
        }

        else if (evt.type === 'final_deliverable') {
          // 最终交付 — 突出显示
          const artifact = evt.data?.artifact
          if (artifact) {
            setFinalDeliverable(artifact)
            setShowFinalDeliverable(true)
            // 同时加入 artifacts 列表(避免重复)
            setArtifacts((prev) => {
              if (prev.find((a) => a.id === artifact.id)) return prev
              return [...prev, artifact]
            })
          }
          if (evt.data?.session_id) {
            setCollabSessionId(evt.data.session_id)
          }
        }

        else if (evt.type === 'chat_done') {
          // 结束 — 记录 session_id
          if (evt.data?.session_id) {
            setCollabSessionId(evt.data.session_id)
          }
        }

        else if (evt.type === 'graph_node_start' || evt.type === 'graph_node_failed' || evt.type === 'graph_checkpoint') {
          // 更新 graphSnapshot
          if (evt.data?.tasks) {
            setGraphSnapshot({ tasks: evt.data.tasks, is_finished: evt.data.is_finished || false })
          } else {
            setGraphSnapshot((prev) => {
              // 局部更新
              return prev
            })
          }
        }

        else if (evt.type === 'handoff') {
          const from = evt.data.from
          const to = evt.data.to
          setHandoffChain((c) => [...c, `${from} → ${to}`])
          setMessages((prev) => [...prev, {
            id: `handoff-${Date.now()}`, role: 'handoff', name: '转交',
            avatar: '', color: '#6B8E6B',
            content: `${from} 转交给 ${to}`, stage: evt.data.reason,
          }])
        }

        else if (evt.type === 'agent_trace') {
          const t = evt.data as AgentTraceData
          setTraces((prev) => ({ ...prev, [t.agent_id]: t }))
        }

        else if (evt.type === 'whiteboard_snapshot') {
          // 主动拉一次白板
          try {
            const wb = await fetchWhiteboard(currentSessionId)
            setWhiteboard(wb)
          } catch { /* ignore */ }
        }

        // === 原有 agent 事件 ===
        else if (evt.type === 'agent_thinking') {
          const a = evt.data
          setThinkingAgent(a)
          currentAgentMsg = {
            id: `a-${a.role}-${Date.now()}`, role: a.role, name: a.name,
            content: '', avatar: a.avatar, color: a.color,
            isStreaming: true, stage: a.stage,
          }
          setMessages((prev) => [...prev, currentAgentMsg!])
        } else if (evt.type === 'agent_chunk') {
          const chunk = evt.data.chunk || ''
          if (currentAgentMsg) {
            const agentId = currentAgentMsg.id
            setMessages((prev) => prev.map((m) => m.id === agentId ? { ...m, content: m.content + chunk } : m))
          }
        } else if (evt.type === 'agent_done') {
          const a = evt.data
          if (currentAgentMsg) {
            const agentId = currentAgentMsg.id
            setMessages((prev) => prev.map((m) => m.id === agentId ? {
              ...m, content: a.content || m.content, isStreaming: false,
              stage: a.stage, final: a.final,
            } : m))
          }
          setThinkingAgent(null)
          currentAgentMsg = null
        } else if (evt.type === 'error') {
          setMessages((prev) => [...prev, {
            id: `e-${Date.now()}`, role: 'error', name: '系统',
            content: evt.data.message || '出错了', avatar: '', color: '#B56B6B',
          }])
        }
      }
    } catch (e: any) {
      setMessages((prev) => [...prev, {
        id: `e-${Date.now()}`, role: 'error', name: '系统',
        content: `连接失败: ${e.message}`, avatar: '', color: '#B56B6B',
      }])
    } finally {
      setIsStreaming(false)
      setThinkingAgent(null)
    }
  }

  const handleClear = () => {
    setMessages([])
    setThinkingAgent(null)
    setGraphSnapshot(null)
    setTraces({})
    setHandoffChain([])
    setWhiteboard(null)
  }

  const handleExport = (fmt: 'markdown' | 'json' | 'text') => {
    exportChat(fmt, messages, currentTeamName)
    setShowExport(false)
  }

  const examples = [
    '帮我分析一下远程办公对团队协作效率的影响',
    '我要写一篇关于 AI 在教育领域应用的报告',
    '帮我策划一个大学生创业项目的推广方案',
    '分析一下这个产品想法：面向独居年轻人的智能陪伴音箱',
  ]

  const ModeIcon = modeMeta.icon

  return (
    <div className="min-h-screen flex flex-col relative">
      <SakuraPetals count={3} />

      {/* 顶栏 */}
      <nav className="sticky top-0 z-50 glass flex-shrink-0">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-soft hover:text-ink transition-colors">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm hidden sm:inline">返回</span>
          </Link>

          {/* 团队选择器 */}
          <button
            onClick={() => setShowTeamPicker(!showTeamPicker)}
            className="flex items-center gap-2 px-4 py-1.5 rounded-full glass hover:bg-surface-hover transition-colors"
          >
            <span className="text-lg">{activeTeam?.icon || activeTeam?.name?.charAt(0) || 'S'}</span>
            <span className="text-sm font-medium">{currentTeamName}</span>
            <span
              className="text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1"
              style={{ backgroundColor: modeMeta.color + '15', color: modeMeta.color }}
            >
              <ModeIcon className="w-3 h-3" />
              {modeMeta.name}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-ink-faint" />
          </button>

          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <>
                {/* 白板按钮 */}
                {whiteboard && (
                  <button
                    onClick={() => setShowWhiteboard(!showWhiteboard)}
                    className="w-9 h-9 flex items-center justify-center rounded-md glass hover:bg-surface-hover transition-colors relative"
                    title="共享白板"
                  >
                    <FileText className="w-4 h-4" />
                    <span className="absolute -top-1 -right-1 text-[9px] w-4 h-4 rounded-full bg-sakura-400 text-white flex items-center justify-center">
                      {whiteboard.artifact_count}
                    </span>
                  </button>
                )}
                {/* Trace 按钮 */}
                {Object.keys(traces).length > 0 && (
                  <button
                    onClick={() => setShowTraces(!showTraces)}
                    className="w-9 h-9 flex items-center justify-center rounded-md glass hover:bg-surface-hover transition-colors relative"
                    title="执行追踪"
                  >
                    <Activity className="w-4 h-4" />
                    <span className="absolute -top-1 -right-1 text-[9px] w-4 h-4 rounded-full bg-sakura-500 text-white flex items-center justify-center">
                      {Object.keys(traces).length}
                    </span>
                  </button>
                )}
                {/* 状态图按钮 */}
                {graphSnapshot && (
                  <button
                    onClick={() => setShowGraphPanel(!showGraphPanel)}
                    className="w-9 h-9 flex items-center justify-center rounded-md glass hover:bg-surface-hover transition-colors"
                    title="任务状态图"
                  >
                    <GitBranch className="w-4 h-4" />
                  </button>
                )}
                {/* 产物按钮(新) */}
                {artifacts.length > 0 && (
                  <button
                    onClick={() => setShowArtifacts(!showArtifacts)}
                    className="w-9 h-9 flex items-center justify-center rounded-md glass hover:bg-surface-hover transition-colors relative"
                    title="协作产物"
                  >
                    <Layers className="w-4 h-4" />
                    <span className="absolute -top-1 -right-1 text-[9px] w-4 h-4 rounded-full bg-clay text-white flex items-center justify-center">
                      {artifacts.length}
                    </span>
                  </button>
                )}
                {/* 最终成果按钮(新) */}
                {finalDeliverable && (
                  <button
                    onClick={() => setShowFinalDeliverable(!showFinalDeliverable)}
                    className="w-9 h-9 flex items-center justify-center rounded-md bg-sage text-white hover:bg-sage-dark transition-colors"
                    title="最终成果"
                  >
                    <Award className="w-4 h-4" />
                  </button>
                )}
                <div className="relative">
                  <button onClick={() => setShowExport(!showExport)} className="w-9 h-9 flex items-center justify-center rounded-md glass hover:bg-surface-hover transition-colors">
                    <Download className="w-4 h-4" />
                  </button>
                  {showExport && (
                    <div className="absolute right-0 top-11 z-30 glass rounded-xl py-1.5 w-36">
                      <button onClick={() => handleExport('markdown')} className="w-full text-left px-4 py-2 text-sm hover:bg-bg-subtle transition-colors">Markdown</button>
                      <button onClick={() => handleExport('text')} className="w-full text-left px-4 py-2 text-sm hover:bg-bg-subtle transition-colors">纯文本</button>
                      <button onClick={() => handleExport('json')} className="w-full text-left px-4 py-2 text-sm hover:bg-bg-subtle transition-colors">JSON</button>
                    </div>
                  )}
                </div>
                <button onClick={handleClear} className="w-9 h-9 flex items-center justify-center rounded-md glass hover:bg-surface-hover transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>

        {/* 团队成员条 + Handoff 链路 */}
        <div className="max-w-7xl mx-auto px-6 pb-2 flex items-center gap-1.5 overflow-x-auto">
          <span className="text-[10px] text-ink-faint flex-shrink-0">成员:</span>
          {currentMembers.map((m, i) => (
            <div key={i} className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] flex-shrink-0"
                 style={{ backgroundColor: m.color + '15', color: m.color }}>
              <span>{m.avatar}</span>
              <span>{m.name}</span>
            </div>
          ))}
          {handoffChain.length > 0 && (
            <>
              <span className="text-[10px] text-ink-faint flex-shrink-0 ml-2">转交:</span>
              {handoffChain.map((h, i) => (
                <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-sage-soft text-sage flex-shrink-0 inline-flex items-center gap-1">
                  <Repeat className="w-3 h-3" /> {h}
                </span>
              ))}
            </>
          )}
        </div>
      </nav>

      {/* 主内容：左消息 + 右侧面板 */}
      <div className="flex-1 flex max-w-7xl mx-auto w-full px-6 py-4 gap-4 relative z-10">
        {/* 左侧：消息流 */}
        <main className="flex-1 pb-40">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[50vh] text-center animate-fade-in">
              <div className="text-5xl mb-4">{activeTeam?.icon || activeTeam?.name?.charAt(0) || 'S'}</div>
              <h2 className="font-display text-2xl font-light mb-2">
                {activeTeam?.name || '选择一个团队开始'}
              </h2>
              <p className="text-sm text-ink-soft mb-8 max-w-md">
                {activeTeam?.description || '从顶部选择预设团队，或去组建你的专属团队'}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                {examples.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(ex)}
                    className="glass rounded-xl p-3 text-left text-xs text-ink-soft hover:text-ink transition-colors"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} />
              ))}
              {thinkingAgent && <ThinkingIndicator agent={thinkingAgent} />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>

        {/* 右侧:状态图 / 白板 / Trace / 产物 / 最终成果 面板 */}
        {(showGraphPanel && graphSnapshot) || showWhiteboard || showTraces || showArtifacts || showFinalDeliverable ? (
          <aside className="w-80 flex-shrink-0 hidden lg:block">
            {showFinalDeliverable && finalDeliverable && (
              <FinalDeliverablePanel artifact={finalDeliverable} onClose={() => setShowFinalDeliverable(false)} />
            )}
            {showArtifacts && (
              <ArtifactsPanel artifacts={artifacts} onClose={() => setShowArtifacts(false)} />
            )}
            {showGraphPanel && graphSnapshot && (
              <GraphPanel snapshot={graphSnapshot} />
            )}
            {showWhiteboard && whiteboard && (
              <WhiteboardPanel data={whiteboard} onClose={() => setShowWhiteboard(false)} />
            )}
            {showTraces && (
              <TracesPanel traces={traces} expanded={expandedTrace} setExpanded={setExpandedTrace} onClose={() => setShowTraces(false)} />
            )}
          </aside>
        ) : null}
      </div>

      {/* 输入区 */}
      <div className="fixed bottom-0 left-0 right-0 z-20">
        <div className="max-w-4xl mx-auto px-6 pb-5">
          <div className="glass rounded-xl p-2 flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder={isStreaming ? '团队协作中...' : '说点什么，召唤你的虚拟团队 →'}
              disabled={isStreaming}
              rows={1}
              className="flex-1 bg-transparent resize-none outline-none px-3 py-2.5 text-sm placeholder-ink-faint max-h-40"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isStreaming || (!activeTeam && !adhocTeam)}
              className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-xl btn-gradient disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-center text-[10px] text-ink-faint mt-2">
            <ModeIcon className="w-3 h-3 inline-block mr-1" style={{ color: modeMeta.color }} />
            {modeMeta.name} · {currentMembers.length || (adhocTeam?.member_ids.length || 0)} 位专家
          </p>
        </div>
      </div>

      {/* 团队选择下拉 */}
      {showTeamPicker && (
        <div className="fixed inset-0 z-40" onClick={() => setShowTeamPicker(false)}>
          <div className="absolute inset-0 bg-ink/10"></div>
          <div className="absolute top-20 left-1/2 -translate-x-1/2 glass rounded-xl p-4 w-[90%] max-w-2xl max-h-[70vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold text-sm mb-3 px-2">选择团队</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {(teams || []).map((t) => {
                const m = MODE_LABELS[t.mode] || MODE_LABELS.group
                const Icon = m.icon
                return (
                  <button
                    key={t.id}
                    onClick={() => { setActiveTeam(t); setAdhocTeam(null); setShowTeamPicker(false); handleClear() }}
                    className={`text-left p-3 rounded-xl transition-all flex items-start gap-3 ${activeTeam?.id === t.id ? 'selected-ring bg-bg-subtle' : 'hover:bg-bg-subtle'}`}
                  >
                    <span className="text-2xl flex-shrink-0">{t.icon || t.name.charAt(0)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm">{t.name}</div>
                      <div className="text-[10px] text-ink-soft line-clamp-2">{t.description}</div>
                      <div className="flex items-center gap-1.5 mt-1.5">
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full flex items-center gap-1"
                              style={{ backgroundColor: m.color + '15', color: m.color }}>
                          <Icon className="w-2.5 h-2.5" />
                          {m.name}
                        </span>
                        {t.tags?.slice(0, 2).map((tag, i) => (
                          <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-full bg-bg-subtle text-ink-faint border border-border">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
            <Link to="/builder" className="block mt-3 p-3 rounded-xl border border-dashed border-border-strong text-center text-sm text-ink-muted hover:bg-bg-subtle transition-colors">
              + 自定义组建团队（7 种协作模式）
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

// ===== 消息气泡 =====

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const isError = msg.role === 'error'
  const isFinal = msg.final
  const isPhase = msg.role === 'phase'
  const isHandoff = msg.role === 'handoff'

  if (isPhase) {
    return (
      <div className="flex justify-center animate-fade-in">
        <div className="px-3 py-1 rounded-full bg-bg-subtle border border-border text-[10px] text-ink-soft flex items-center gap-1.5">
          <Clock className="w-3 h-3" />
          {msg.stage ? <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" />{msg.stage}</span> : '阶段切换'}
        </div>
      </div>
    )
  }

  if (isHandoff) {
    return (
      <div className="flex justify-center animate-fade-in">
        <div className="px-4 py-1.5 rounded-full bg-sage-soft border border-sage-soft text-[11px] text-sage flex items-center gap-2">
          <Repeat className="w-3 h-3" /> {msg.content}
        </div>
      </div>
    )
  }

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-up">
        <div className="flex items-start gap-2.5 max-w-[75%]">
          <div className="btn-gradient rounded-xl rounded-tr-md px-4 py-2.5">
            <p className="msg-content text-sm text-surface">{msg.content}</p>
          </div>
          <div className="w-9 h-9 rounded-md flex items-center justify-center text-sm font-mono font-semibold text-surface flex-shrink-0 bg-ink">
            {msg.avatar || '我'}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex items-start gap-2.5 animate-fade-up ${isFinal ? 'mt-4' : ''}`}>
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center text-lg flex-shrink-0 border border-border bg-bg-subtle"
        style={{ backgroundColor: msg.color + '15' }}
      >
        {msg.avatar}
      </div>
      <div className="max-w-[78%] flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium" style={{ color: msg.color }}>{msg.name}</span>
          {msg.stage && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-hover text-ink-faint">{msg.stage}</span>
          )}
          {isFinal && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-sakura-100 text-sakura-600 font-medium">最终成果</span>
          )}
          {msg.isStreaming && (
            <span className="text-[10px] text-ink-faint inline-flex gap-0.5">
              <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
            </span>
          )}
        </div>
        <div className={`rounded-xl rounded-tl-md px-4 py-2.5 ${isError ? 'bg-clay-soft border border-clay-soft' : isFinal ? 'glass-dark' : 'glass'}`}>
          <p className={`msg-content text-sm ${isFinal ? 'text-white' : isError ? 'text-clay' : 'text-ink'}`}>
            {isError && <AlertCircle className="w-3 h-3 inline-block mr-1" />}
            {msg.content || (msg.isStreaming ? <span className="text-ink-faint italic text-xs">正在组织语言...</span> : '')}
          </p>
        </div>
      </div>
    </div>
  )
}

// ===== 思考指示器 =====

function ThinkingIndicator({ agent }: { agent: any }) {
  return (
    <div className="flex items-start gap-2.5 animate-fade-in">
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center text-lg flex-shrink-0 animate-breathe border border-border bg-bg-subtle"
        style={{ backgroundColor: agent.color + '15' }}
      >
        {agent.avatar}
      </div>
      <div className="flex items-center gap-2 mt-1.5">
        <span className="text-sm font-medium" style={{ color: agent.color }}>{agent.name}</span>
        {agent.stage && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-hover text-ink-faint">{agent.stage}</span>}
        <span className="text-[10px] text-ink-faint inline-flex gap-0.5 items-center">
          思考中
          <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
        </span>
      </div>
    </div>
  )
}

// ===== 状态图面板（LangGraph 风格） =====

function GraphPanel({ snapshot }: { snapshot: GraphSnapshot }) {
  return (
    <div className="glass rounded-xl p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-sakura-400" />
        <h3 className="font-semibold text-sm">任务状态图</h3>
        <span className="text-[10px] text-ink-faint ml-auto">
          {(snapshot.tasks || []).filter(t => t.state === 'done').length} / {(snapshot.tasks || []).length} 已完成
        </span>
      </div>
      <div className="space-y-1.5 max-h-[60vh] overflow-y-auto pr-1">
        {(snapshot.tasks || []).map((task) => {
          const color = TASK_STATE_COLORS[task.state] || '#A8A299'
          return (
            <div
              key={task.id}
              className="p-2.5 rounded-xl bg-bg-subtle border-l-2 transition-all"
              style={{ borderColor: color }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: color, animation: task.state === 'running' ? 'pulse 1.5s infinite' : 'none' }}
                />
                <span className="text-xs font-medium flex-1 truncate">{task.name}</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded-full" style={{ backgroundColor: color + '15', color }}>
                  {task.state}
                </span>
              </div>
              <div className="text-[10px] text-ink-faint flex items-center gap-1.5">
                <span>@{task.agent_id}</span>
                {task.dependencies.length > 0 && (
                  <span className="text-ink-faint">· 依赖 {task.dependencies.join(', ')}</span>
                )}
              </div>
              {task.output_preview && (
                <p className="text-[10px] text-ink-soft mt-1.5 line-clamp-2">{task.output_preview}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ===== 白板面板（MetaGPT 风格） =====

function WhiteboardPanel({ data, onClose }: { data: WhiteboardData; onClose: () => void }) {
  return (
    <div className="glass rounded-xl p-4 mb-4">
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-4 h-4 text-amber" />
        <h3 className="font-semibold text-sm">共享白板</h3>
        <span className="text-[10px] text-ink-faint ml-auto">{data.artifact_count} 个产物</span>
        <button onClick={onClose} aria-label="关闭" className="text-ink-faint hover:text-ink w-7 h-7 flex items-center justify-center rounded-md hover:bg-bg-subtle transition-colors">
          <X className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      </div>
      <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
        {(data.artifacts || []).map((a) => (
          <details key={a.id} className="bg-bg-subtle rounded-xl p-2.5">
            <summary className="cursor-pointer text-xs font-medium flex items-center gap-1.5">
              <FileText className="w-3 h-3" />
              <span className="flex-1">{a.agent_name}</span>
              <span className="text-[9px] text-ink-faint">{a.type}</span>
            </summary>
            <p className="text-[10px] text-ink-soft mt-2 whitespace-pre-wrap leading-relaxed">{a.content}</p>
            {(a.tags || []).length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {(a.tags || []).map((t, i) => (
                  <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-full bg-surface-hover text-ink-faint">
                    #{t}
                  </span>
                ))}
              </div>
            )}
          </details>
        ))}
      </div>
    </div>
  )
}

// ===== Trace 面板（Smolagents 风格） =====

function TracesPanel({ traces, expanded, setExpanded, onClose }: {
  traces: Record<string, AgentTraceData>, expanded: string | null,
  setExpanded: (id: string | null) => void, onClose: () => void,
}) {
  const entries = Object.values(traces)
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-ink-muted" />
        <h3 className="font-semibold text-sm">执行追踪</h3>
        <span className="text-[10px] text-ink-faint ml-auto">{entries.length} 个 agent</span>
        <button onClick={onClose} aria-label="关闭" className="text-ink-faint hover:text-ink w-7 h-7 flex items-center justify-center rounded-md hover:bg-bg-subtle transition-colors">
          <X className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      </div>
      <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
        {entries.map((t) => {
          const isExpanded = expanded === t.agent_id
          return (
            <div key={t.agent_id} className="bg-bg-subtle rounded-xl overflow-hidden">
              <button
                onClick={() => setExpanded(isExpanded ? null : t.agent_id)}
                className="w-full p-2.5 text-left flex items-center gap-2"
              >
                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                <span className="text-xs font-medium flex-1">{t.agent_name}</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-bg-subtle text-ink-soft">
                  {t.step_count} 步
                </span>
              </button>
              {isExpanded && (
                <div className="px-3 pb-3 space-y-1.5">
                  {(t.steps || []).map((s) => {
                    const icon = s.type === 'think' ? <MessageSquare className="w-3 h-3" /> : s.type === 'tool' ? <Wrench className="w-3 h-3" /> : s.type === 'observe' ? <Eye className="w-3 h-3" /> : <Upload className="w-3 h-3" />
                    return (
                      <div key={s.step} className="flex items-start gap-1.5 text-[10px]">
                        <span className="font-mono text-ink-faint w-4">{s.step}</span>
                        <span>{icon}</span>
                        <span className="flex-1 text-ink-soft line-clamp-3">{s.content}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ===== 最终成果面板(新) =====

function FinalDeliverablePanel({ artifact, onClose }: { artifact: CollabArtifact; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const onCopy = () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(artifact.content).catch(() => {})
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }
  return (
    <div className="glass rounded-xl p-4 border-2 border-sage/30">
      <div className="flex items-center gap-2 mb-3">
        <Award className="w-4 h-4 text-sage" />
        <h3 className="font-semibold text-sm">最终成果</h3>
        <span className="text-[10px] text-sage font-mono ml-auto">FINAL</span>
        <button onClick={onClose} aria-label="关闭" className="text-ink-faint hover:text-ink w-7 h-7 flex items-center justify-center rounded-md hover:bg-bg-subtle transition-colors">
          <X className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      </div>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-sage-soft text-sage font-mono">
          {artifact.type}
        </span>
        <span className="text-[10px] text-ink-faint">由 {artifact.agent_name} 生成</span>
        <button onClick={onCopy} className="text-[10px] text-ink-faint hover:text-ink ml-auto font-mono">
          {copied ? '已复制' : '复制'}
        </button>
      </div>
      <div className="bg-bg-subtle rounded-md p-3 max-h-[60vh] overflow-y-auto">
        <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono text-ink-soft">
{artifact.content}
        </pre>
      </div>
      {artifact.summary && artifact.summary !== artifact.content.slice(0, 120) && (
        <div className="mt-2 px-2 py-1.5 rounded-md bg-sage/5 border border-sage/15">
          <p className="text-[10px] text-sage leading-relaxed">{artifact.summary}</p>
        </div>
      )}
    </div>
  )
}

// ===== 产物列表面板(新) =====

function ArtifactsPanel({ artifacts, onClose }: { artifacts: CollabArtifact[]; onClose: () => void }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Layers className="w-4 h-4 text-clay" />
        <h3 className="font-semibold text-sm">协作产物</h3>
        <span className="text-[10px] text-ink-faint ml-auto">{artifacts.length} 个</span>
        <button onClick={onClose} aria-label="关闭" className="text-ink-faint hover:text-ink w-7 h-7 flex items-center justify-center rounded-md hover:bg-bg-subtle transition-colors">
          <X className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      </div>
      <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
        {artifacts.map((a) => {
          const isExpanded = expanded === a.id
          const isFinal = a.type === 'final_report'
          return (
            <div
              key={a.id}
              className={`bg-bg-subtle rounded-xl overflow-hidden ${isFinal ? 'border border-sage/30' : ''}`}
            >
              <button
                onClick={() => setExpanded(isExpanded ? null : a.id)}
                className="w-full p-2.5 text-left flex items-center gap-2"
              >
                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                <span className="text-xs font-medium flex-1">{a.title}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-mono ${
                  isFinal ? 'bg-sage-soft text-sage' : 'bg-bg-subtle text-ink-soft'
                }`}>
                  {a.type}
                </span>
              </button>
              {isExpanded && (
                <div className="px-3 pb-3">
                  <p className="text-[10px] text-ink-faint mb-2">由 {a.agent_name} 生成</p>
                  <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono text-ink-soft max-h-80 overflow-y-auto">
{a.content}
                  </pre>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
