import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles, Bot, Code, Brain, Clock, CheckCircle, Play, BookOpen } from 'lucide-react'

// Agent role display info
const AGENT_ROLES = [
  { name: '需求分析 Agent', desc: '分析用户需求并生成 PRD 文档', icon: BookOpen, color: 'blue' },
  { name: '架构设计 Agent', desc: '设计系统架构和 API 接口规范', icon: Sparkles, color: 'purple' },
  { name: '前端开发 Agent', desc: '生成 React + Tailwind 前端组件', icon: Code, color: 'cyan' },
  { name: '后端开发 Agent', desc: '生成 FastAPI 后端服务和数据模型', icon: Bot, color: 'emerald' },
  { name: '测试验证 Agent', desc: '生成自动化测试并验证功能', icon: CheckCircle, color: 'amber' },
  { name: '代码审查 Agent', desc: '审查生成代码的质量和安全性', icon: Brain, color: 'indigo' },
  { name: '部署 Agent', desc: '生成 Docker 配置并准备部署', icon: Play, color: 'rose' },
]

export default function HomePage() {
  const [sessions, setSessions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState<any>(null)

  useEffect(() => {
    // Load sessions list
    fetchSessions()
    // Load health
    fetch('/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'error' }))
  }, [])

  async function fetchSessions() {
    try {
      const res = await fetch('/api/v1/sessions')
      if (res.ok) {
        const data = await res.json()
        setSessions(data.data || [])
      }
    } catch (e) {
      console.error('Failed to load sessions:', e)
    } finally {
      setLoading(false)
    }
  }

  function getStatusBadge(status: string) {
    const styles: Record<string, string> = {
      completed: 'bg-green-100 text-green-800 border-green-200',
      running: 'bg-blue-100 text-blue-800 border-blue-200',
      failed: 'bg-red-100 text-red-800 border-red-200',
      cancelled: 'bg-gray-100 text-gray-800 border-gray-200',
      created: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    }
    const labels: Record<string, string> = {
      completed: '已完成',
      running: '执行中',
      failed: '失败',
      cancelled: '已取消',
      created: '已创建',
    }
    return (
      <span className={`text-xs px-2 py-1 rounded-full border ${styles[status] || styles.created}`}>
        {labels[status] || status}
      </span>
    )
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Hero */}
      <div className="bg-gradient-to-br from-blue-600 via-purple-600 to-purple-700 text-white py-16 px-6 text-center relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="grid grid-cols-8 gap-1 h-full">
            {Array.from({ length: 64 }).map((_, i) => (
              <div key={i} className="bg-white/10 rounded-sm" />
            ))}
          </div>
        </div>
        <div className="relative">
          <h1 className="text-5xl font-bold mb-4">多智能体全栈开发系统</h1>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            描述你的需求，多个 Agent 将协同工作，自动生成完整的前后端应用
          </p>
          <Link
            to="/new-task"
            className="inline-flex items-center gap-2 bg-white text-purple-700 font-semibold px-8 py-3 rounded-lg shadow-xl hover:shadow-2xl transition-all hover:-translate-y-0.5"
          >
            <Sparkles className="w-5 h-5" />
            开始新任务
          </Link>
          <div className="mt-8 flex items-center justify-center gap-8 text-sm text-blue-100">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4" />
              <span>后端服务 {health?.status === 'healthy' ? <span className="text-green-200">已就绪</span> : <span className="text-yellow-200">等待启动</span>}</span>
            </div>
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4" />
              <span>{AGENT_ROLES.length} 个 Agent 协同工作</span>
            </div>
          </div>
        </div>
      </div>

      {/* Agent roles */}
      <section className="py-12 px-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2 text-center">协同工作流程</h2>
        <p className="text-gray-500 text-center mb-8">多个专业 Agent 按序执行，每个专注于自己的领域</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {AGENT_ROLES.map((role, idx) => {
            const Icon = role.icon
            return (
              <div key={role.name} className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700 flex gap-4 items-start shadow-sm hover:shadow-md transition-shadow">
                <div className="flex-shrink-0">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white bg-${role.color}-600`} style={{
                    backgroundColor: role.color === 'blue' ? '#2563eb' : role.color === 'purple' ? '#9333ea' : role.color === 'cyan' ? '#0891b2' : role.color === 'emerald' ? '#059669' : role.color === 'amber' ? '#d97706' : role.color === 'indigo' ? '#4f46e5' : '#e11d48'
                  }}>
                    <Icon className="w-5 h-5" />
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-800 dark:text-gray-100">{role.name}</span>
                    <span className="text-xs text-gray-400">#{idx + 1}</span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">{role.desc}</p>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Recent sessions */}
      <section className="py-12 px-6 bg-gray-100 dark:bg-gray-900/50">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-100">最近任务</h2>
          <button onClick={fetchSessions} className="text-sm text-blue-600 hover:text-blue-700">
            刷新
          </button>
        </div>

        {loading ? (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-12 text-center text-gray-500 border border-gray-200 dark:border-gray-700">
            加载中...
          </div>
        ) : sessions.length === 0 ? (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-12 text-center border border-gray-200 dark:border-gray-700">
            <Clock className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 mb-4">暂无任务记录</p>
            <Link to="/new-task" className="inline-block bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
              创建第一个任务
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.slice(0, 10).map((session: any) => (
              <Link
                to={`/session?id=${session.id}`}
                key={session.id}
                className="block bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 hover:border-blue-400 transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-800 dark:text-gray-100 truncate">{session.requirement}</p>
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                      <span>{session.id.slice(0, 12)}</span>
                      <span>·</span>
                      <span>{new Date(session.created_at).toLocaleString()}</span>
                      <span>·</span>
                      <span>
                        {Object.entries(session.agent_progress || {}).filter(([, p]: any) => p.status === 'completed').length}/
                        {Object.keys(session.agent_progress || {}).length} 个 Agent 完成
                      </span>
                    </div>
                  </div>
                  <div className="flex-shrink-0">{getStatusBadge(session.status)}</div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="py-8 text-center text-sm text-gray-400">
        <p>SakuraAgentTeam · 多智能体全栈开发系统</p>
      </footer>
    </div>
  )
}
