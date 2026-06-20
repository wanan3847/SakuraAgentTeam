import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Clock, CheckCircle, XCircle, AlertTriangle, FileCode, BookOpen, Server, Shield, Play, RotateCcw, ExternalLink } from 'lucide-react'
import CodeBlock from '../components/CodeBlock'

// Agent role metadata for display
const AGENT_INFO: Record<string, { name: string; icon: React.ComponentType<any>; color: string; description: string }> = {
  requirements: { name: '需求分析', icon: BookOpen, color: 'blue', description: '分析需求并生成 PRD 文档' },
  design: { name: '架构设计', icon: Server, color: 'purple', description: '设计系统架构和 API 接口' },
  frontend: { name: '前端开发', icon: FileCode, color: 'cyan', description: '生成 React + Tailwind 前端代码' },
  backend: { name: '后端开发', icon: Server, color: 'emerald', description: '生成 FastAPI 后端代码和路由' },
  testing: { name: '测试验证', icon: CheckCircle, color: 'amber', description: '生成单元测试和集成测试' },
  review: { name: '代码审查', icon: Shield, color: 'indigo', description: '审查代码质量和安全问题' },
  deployment: { name: '部署配置', icon: Play, color: 'rose', description: '生成 Docker 部署配置' },
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'bg-green-500'
    case 'running': return 'bg-blue-500 animate-pulse'
    case 'failed': return 'bg-red-500'
    case 'skipped': return 'bg-gray-400'
    default: return 'bg-gray-300'
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case 'completed': return '已完成'
    case 'running': return '执行中'
    case 'failed': return '失败'
    case 'skipped': return '已跳过'
    default: return '等待中'
  }
}

export default function SessionPage() {
  const params = new URLSearchParams(window.location.search)
  const sessionId = params.get('id') || ''
  const navigate = useNavigate()
  const [session, setSession] = useState<any>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedArtifact, setSelectedArtifact] = useState<any>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<any>(null)

  // Auto scroll logs to bottom
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // Load session data
  useEffect(() => {
    if (!sessionId) {
      alert('Session ID is required')
      navigate('/')
      return
    }

    // Initial fetch
    fetchSession()

    // SSE event stream
    setupEventStream()

    // Poll session status every 2 seconds
    const interval = setInterval(fetchSession, 2000)

    return () => {
      clearInterval(interval)
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [sessionId])

  async function fetchSession() {
    try {
      const res = await fetch(`/api/v1/sessions/${sessionId}`)
      if (res.ok) {
        const data = await res.json()
        setSession(data.data)
      }
    } catch (e) {
      console.error('Failed to fetch session:', e)
    } finally {
      setLoading(false)
    }
  }

  function setupEventStream() {
    try {
      const eventSource = new EventSource(`/api/v1/sessions/${sessionId}/stream`)
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        // Handle generic messages
      }

      eventSource.addEventListener('agent.log', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          setLogs((prev) => [...prev, { type: 'log', ...data, timestamp: data.timestamp || new Date().toISOString() }])
        } catch (e) {
          console.error('Parse error:', e)
        }
      })

      eventSource.addEventListener('agent.started', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          setLogs((prev) => [...prev, { type: 'agent_start', ...data, timestamp: data.timestamp || new Date().toISOString() }])
        } catch (e) {
          console.error('Parse error:', e)
        }
      })

      eventSource.addEventListener('agent.completed', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          setLogs((prev) => [...prev, { type: 'agent_complete', ...data, timestamp: data.timestamp || new Date().toISOString() }])
        } catch (e) {
          console.error('Parse error:', e)
        }
      })

      eventSource.addEventListener('agent.failed', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          setLogs((prev) => [...prev, { type: 'agent_failed', ...data, timestamp: data.timestamp || new Date().toISOString() }])
        } catch (e) {
          console.error('Parse error:', e)
        }
      })

      eventSource.addEventListener('session.started', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          setLogs((prev) => [...prev, { type: 'session_start', message: `Workflow ${data.workflow} started (${data.steps?.length || 0} steps)`, timestamp: data.timestamp || new Date().toISOString() }])
        } catch (e) {
          console.error('Parse error:', e)
        }
      })

      eventSource.addEventListener('session.completed', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          setLogs((prev) => [...prev, { type: 'session_complete', message: `Session completed successfully (${data.artifacts_count || 0} artifacts)`, timestamp: data.timestamp || new Date().toISOString() }])
        } catch (e) {
          console.error('Parse error:', e)
        }
      })

      eventSource.addEventListener('session.failed', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          setLogs((prev) => [...prev, { type: 'session_failed', message: `Session failed: ${data.error || 'Unknown error'}`, timestamp: data.timestamp || new Date().toISOString() }])
        } catch (e) {
          console.error('Parse error:', e)
        }
      })

      eventSource.onerror = () => {
        console.log('EventSource connection issue')
      }
    } catch (e) {
      console.error('Failed to setup SSE:', e)
    }
  }

  async function handleExecute() {
    if (!sessionId) return
    try {
      await fetch(`/api/v1/sessions/${sessionId}/execute`, { method: 'POST' })
      setLogs((prev) => [...prev, { type: 'info', message: 'Manual execution started', timestamp: new Date().toISOString() }])
    } catch (e) {
      console.error('Execute failed:', e)
    }
  }

  async function handleCancel() {
    if (!sessionId) return
    try {
      await fetch(`/api/v1/sessions/${sessionId}/cancel`, { method: 'POST' })
    } catch (e) {
      console.error('Cancel failed:', e)
    }
  }

  if (loading && !session) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="animate-pulse text-gray-500">加载中...</div>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="text-center py-12">
          <h2 className="text-xl font-bold text-gray-800 mb-2">会话未找到</h2>
          <Link to="/new-task" className="text-blue-600 hover:underline">创建新任务 →</Link>
        </div>
      </div>
    )
  }

  const agentProgress = session.agent_progress || {}
  const artifacts = session.artifacts || []

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <Link to="/" className="text-sm text-blue-600 hover:underline mb-2 inline-block">← 返回</Link>
          <h1 className="text-2xl font-bold text-gray-800">会话详情</h1>
          <p className="text-gray-500 mt-1">ID: {session.id}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleExecute} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <RotateCcw className="w-4 h-4" />
            重新执行
          </button>
          <button onClick={handleCancel} className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
            <XCircle className="w-4 h-4" />
            取消
          </button>
        </div>
      </div>

      {/* Requirement */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-2">需求</h2>
        <p className="text-gray-800">{session.requirement}</p>
        <div className="mt-3 flex items-center gap-3 text-sm">
          <span className={`px-3 py-1 rounded-full font-medium ${
            session.status === 'completed' ? 'bg-green-100 text-green-800' :
            session.status === 'running' ? 'bg-blue-100 text-blue-800' :
            session.status === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {getStatusLabel(session.status)}
          </span>
          <span className="text-gray-400 flex items-center gap-1">
            <Clock className="w-4 h-4" />
            {session.created_at}
          </span>
        </div>
      </div>

      {/* Agent progress */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">Agent 执行流程</h2>
          <div className="space-y-3">
            {Object.entries(AGENT_INFO).map(([role, info]) => {
              const progress = agentProgress[role] || { status: 'pending' }
              const Icon = info.icon
              const statusColor = getStatusColor(progress.status)

              return (
                <div key={role} className="flex items-center gap-4 p-3 border border-gray-100 rounded-lg bg-gray-50">
                  <div className={`w-8 h-8 rounded-full ${statusColor} flex items-center justify-center text-white flex-shrink-0`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-800">{info.name}</div>
                    <div className="text-xs text-gray-500 truncate">{info.description}</div>
                  </div>
                  <div className="text-right text-sm flex-shrink-0">
                    <div className={`font-medium ${
                      progress.status === 'completed' ? 'text-green-700' :
                      progress.status === 'running' ? 'text-blue-700' :
                      progress.status === 'failed' ? 'text-red-700' :
                      'text-gray-600'
                    }`}>{getStatusLabel(progress.status)}</div>
                    {progress.completed_at && (
                      <div className="text-xs text-gray-400">{new Date(progress.completed_at).toLocaleString()}</div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Logs */}
        <div className="bg-white border border-gray-200 rounded-lg p-6 max-h-[600px] overflow-hidden flex flex-col">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">实时日志</h2>
          <div className="flex-1 overflow-y-auto text-sm font-mono bg-gray-900 text-gray-100 p-3 rounded">
            {logs.length === 0 ? (
              <div className="text-gray-500 italic">等待执行...</div>
            ) : (
              <div className="space-y-1">
                {logs.map((log, idx) => (
                  <div key={idx} className="leading-relaxed">
                    <span className="text-gray-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                    {log.type === 'agent_start' && <span className="text-blue-400">▶ {log.payload?.agent_role} started</span>}
                    {log.type === 'agent_complete' && <span className="text-green-400">✓ {log.payload?.agent_role} completed - {log.payload?.artifact || ''}</span>}
                    {log.type === 'agent_failed' && <span className="text-red-400">✗ {log.payload?.agent_role} FAILED</span>}
                    {log.type === 'session_start' && <span className="text-cyan-400">{log.message}</span>}
                    {log.type === 'session_complete' && <span className="text-green-400">{log.message}</span>}
                    {log.type === 'session_failed' && <span className="text-red-400">{log.message}</span>}
                    {log.type === 'log' && (
                      <span>
                        <span className="text-yellow-400">[{log.payload?.agent_role || 'system'}]</span> {log.payload?.message || ''}
                      </span>
                    )}
                    {log.type === 'info' && <span className="text-white">{log.message}</span>}
                    {log.type === 'artifact.created' && <span className="text-purple-400">📦 Artifact created: {log.payload?.name}</span>}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Artifacts */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">产物 ({artifacts.length})</h2>
        {artifacts.length === 0 ? (
          <div className="text-gray-500 italic py-8 text-center">暂无产物</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {artifacts.map((artifact: any, idx: number) => (
              <div
                key={idx}
                className={`text-left p-4 rounded-lg border hover:border-blue-400 transition-all ${
                  selectedArtifact === artifact ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-gray-50'
                }`}
              >
                <button
                  onClick={() => setSelectedArtifact(artifact)}
                  className="w-full text-left"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <FileCode className="w-4 h-4 text-blue-500" />
                    <span className="font-medium text-gray-800">{artifact.name}</span>
                  </div>
                  <div className="text-xs text-gray-500">{artifact.agent_role} · {artifact.type}</div>
                  <div className="text-xs text-gray-400 mt-2 truncate">
                    {typeof artifact.content === 'string' ? artifact.content.slice(0, 120) : ''}...
                  </div>
                </button>
                {artifact.metadata?.path && (
                  <Link
                    to={`/artifacts/${sessionId}?file=${encodeURIComponent(artifact.metadata.path)}`}
                    className="mt-2 inline-flex items-center gap-1 text-xs text-sky-600 hover:underline"
                  >
                    <ExternalLink className="w-3 h-3" />
                    在产物浏览器中打开
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Artifact detail view */}
      {selectedArtifact && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-700">{selectedArtifact.name}</h2>
            <button onClick={() => setSelectedArtifact(null)} className="text-gray-500 hover:text-gray-700 text-sm">关闭</button>
          </div>
          <div className="text-sm text-gray-500 mb-3">
            {selectedArtifact.agent_role} · {selectedArtifact.type}
          </div>
          <CodeBlock
            code={typeof selectedArtifact.content === 'string' ? selectedArtifact.content : ''}
            filename={selectedArtifact.name}
            maxHeight="500px"
          />
        </div>
      )}
    </div>
  )
}
