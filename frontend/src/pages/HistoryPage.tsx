import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSessions, cancelSession, type Session } from '../services/api'
import {
  History as HistoryIcon,
  RotateCcw,
  XCircle,
  CheckCircle,
  Clock,
  Trash2,
} from 'lucide-react'

function statusBadge(status: string) {
  const map: Record<string, { cls: string; label: string }> = {
    completed: { cls: 'bg-green-100 text-green-800 border-green-200', label: '已完成' },
    running: { cls: 'bg-blue-100 text-blue-800 border-blue-200 animate-pulse', label: '执行中' },
    failed: { cls: 'bg-red-100 text-red-800 border-red-200', label: '失败' },
    cancelled: { cls: 'bg-gray-100 text-gray-800 border-gray-200', label: '已取消' },
    created: { cls: 'bg-yellow-100 text-yellow-800 border-yellow-200', label: '已创建' },
  }
  const v = map[status] || map.created
  return (
    <span className={`text-xs px-2 py-1 rounded-full border ${v.cls}`}>{v.label}</span>
  )
}

export default function HistoryPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed' | 'running' | 'cancelled' | 'created'>('all')
  const [keyword, setKeyword] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const r = await listSessions()
      setSessions((r.data as Session[]) || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = sessions.filter((s) => {
    if (filter !== 'all' && s.status !== filter) return false
    if (keyword && !s.requirement.toLowerCase().includes(keyword.toLowerCase())) return false
    return true
  })

  const onCancel = async (id: string) => {
    if (!confirm(`确定取消 session ${id.slice(0, 12)}…?`)) return
    try {
      await cancelSession(id)
      await load()
    } catch (e) {
      console.error(e)
    }
  }

  const total = sessions.length
  const counts = {
    completed: sessions.filter((s) => s.status === 'completed').length,
    failed: sessions.filter((s) => s.status === 'failed').length,
    running: sessions.filter((s) => s.status === 'running').length,
    cancelled: sessions.filter((s) => s.status === 'cancelled').length,
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <HistoryIcon className="w-6 h-6" />
            Session 历史
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            所有执行过的任务，可一键恢复或跳转到产物
          </p>
        </div>
        <Link to="/" className="text-sm text-sky-600 dark:text-sky-400 hover:underline">
          ← 返回首页
        </Link>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-6 space-y-4">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <div className="text-xs text-slate-500">总数</div>
            <div className="text-2xl font-semibold">{total}</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <div className="text-xs text-slate-500">已完成</div>
            <div className="text-2xl font-semibold text-green-600">{counts.completed}</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <div className="text-xs text-slate-500">执行中</div>
            <div className="text-2xl font-semibold text-blue-600">{counts.running}</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <div className="text-xs text-slate-500">失败</div>
            <div className="text-2xl font-semibold text-red-600">{counts.failed}</div>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <div className="text-xs text-slate-500">已取消</div>
            <div className="text-2xl font-semibold text-slate-500">{counts.cancelled}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4 flex flex-wrap items-center gap-3">
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索需求关键字…"
            className="flex-1 min-w-[200px] px-3 py-2 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm"
          />
          <div className="flex gap-1">
            {(['all', 'completed', 'running', 'failed', 'cancelled', 'created'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`px-3 py-1.5 text-xs rounded ${
                  filter === s
                    ? 'bg-sky-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
                }`}
              >
                {s === 'all' ? '全部' : s === 'completed' ? '已完成' : s === 'running' ? '执行中' : s === 'failed' ? '失败' : s === 'created' ? '已创建' : '已取消'}
              </button>
            ))}
          </div>
          <button
            onClick={load}
            className="text-sm text-sky-600 dark:text-sky-400 hover:underline"
          >
            刷新
          </button>
        </div>

        {/* List */}
        {loading ? (
          <div className="text-sm text-slate-500 text-center py-12">加载中…</div>
        ) : filtered.length === 0 ? (
          <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-12 text-center text-slate-500">
            <Clock className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            {sessions.length === 0 ? '暂无任务，去' : '没有匹配的 session。'}
            {sessions.length === 0 && (
              <>
                {' '}
                <Link to="/new-task" className="text-sky-600 hover:underline">
                  创建一个
                </Link>
              </>
            )}
          </div>
        ) : (
          <ul className="space-y-2">
            {filtered.map((s) => {
              const completedCount = 0 // unknown in list view
              return (
                <li
                  key={s.id}
                  className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4 flex items-start gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      {statusBadge(s.status)}
                      <span className="text-xs font-mono text-slate-500">{s.id.slice(0, 12)}</span>
                      <span className="text-xs text-slate-400">
                        {new Date(s.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="text-sm text-slate-800 dark:text-slate-200 truncate">
                      {s.requirement}
                    </div>
                    {s.error && (
                      <div className="text-xs text-red-600 dark:text-red-400 mt-1 truncate">
                        错误：{s.error}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <Link
                      to={`/session?id=${s.id}`}
                      className="text-xs px-3 py-1.5 rounded border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700/50"
                      title="查看详情"
                    >
                      详情
                    </Link>
                    <Link
                      to={`/artifacts/${s.id}`}
                      className="text-xs px-3 py-1.5 rounded border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700/50"
                      title="查看产物"
                    >
                      产物
                    </Link>
                    {(s.status === 'created' || s.status === 'running') && (
                      <button
                        onClick={() => onCancel(s.id)}
                        className="text-xs px-3 py-1.5 rounded border border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                        title="取消执行"
                      >
                        取消
                      </button>
                    )}
                    {s.status === 'completed' && (
                      <Link
                        to={`/session?id=${s.id}&rerun=1`}
                        className="text-xs px-3 py-1.5 rounded border border-sky-300 text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-900/20"
                        title="一键恢复（同需求重跑）"
                      >
                        <RotateCcw className="w-3 h-3 inline" /> 恢复
                      </Link>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </main>
    </div>
  )
}
