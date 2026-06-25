import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Trash2, MessageCircle, Users, Clock, ChevronDown, ChevronRight, Loader2, LogIn, Lock, FileText } from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import { useAuth } from '../contexts/AuthContext'
import { fetchHistory, fetchHistoryDetail, deleteHistory, HistoryItem, HistoryDetail } from '../lib/historyApi'

const PAGE_SIZE = 20

export default function HistoryPage() {
  const { user, token } = useAuth()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<HistoryDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async (p: number) => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const { items, total } = await fetchHistory(token, p, PAGE_SIZE)
      setItems(items)
      setTotal(total)
    } catch (e: any) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (token) load(1)
  }, [token, load])

  const handleExpand = async (item: HistoryItem) => {
    if (expandedId === item.id) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(item.id)
    setDetail(null)
    if (!token) return
    setDetailLoading(true)
    try {
      const d = await fetchHistoryDetail(token, item.id)
      setDetail(d)
    } catch (e: any) {
      setError(e.message || '加载详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!token) return
    if (!confirm('确定删除这条历史记录？')) return
    try {
      await deleteHistory(token, id)
      setItems((prev) => prev.filter((i) => i.id !== id))
      setTotal((t) => Math.max(0, t - 1))
      if (expandedId === id) {
        setExpandedId(null)
        setDetail(null)
      }
    } catch (e: any) {
      setError(e.message || '删除失败')
    }
  }

  const handleClearAll = async () => {
    if (!token) return
    if (!confirm('确定清空所有历史记录？此操作不可恢复。')) return
    try {
      // 逐条删除
      for (const it of items) {
        await deleteHistory(token, it.id)
      }
      setItems([])
      setTotal(0)
      setExpandedId(null)
      setDetail(null)
    } catch (e: any) {
      setError(e.message || '清空失败')
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  // 未登录
  if (!user || !token) {
    return (
      <div className="aurora-bg min-h-screen relative flex items-center justify-center px-4">
        <SakuraPetals count={4} />
        <div className="glass rounded-xl p-10 max-w-md w-full text-center relative z-10 animate-fade-up">
          <div className="w-12 h-12 mx-auto mb-4 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
            <Lock className="w-6 h-6 text-ink-muted" />
          </div>
          <h1 className="font-display text-2xl font-light mb-2">
            <span className="text-ink font-medium">请先登录</span>
          </h1>
          <p className="text-sm text-ink-soft mb-6">登录后即可查看你的历史协作记录</p>
          <Link to="/auth" className="btn-gradient inline-flex items-center gap-2 px-6 py-3 rounded-md font-medium">
            <LogIn className="w-4 h-4" /> 去登录
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="aurora-bg min-h-screen relative">
      <SakuraPetals count={3} />

      {/* 顶栏 */}
      <nav className="sticky top-0 z-50 glass">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-soft hover:text-ink transition-colors">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回</span>
          </Link>
          <h1 className="font-bold text-lg text-ink font-medium">历史记录</h1>
          {items.length > 0 ? (
            <button
              onClick={handleClearAll}
              className="flex items-center gap-1.5 text-xs text-clay hover:text-clay transition-colors px-3 py-1.5 rounded-md hover:bg-clay-soft"
            >
              <Trash2 className="w-3.5 h-3.5" /> 清空
            </button>
          ) : (
            <div className="w-16" />
          )}
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8 relative z-10">
        {error && (
          <div className="mb-4 text-xs text-clay bg-clay-soft border border-clay-soft rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-ink-muted" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20 animate-fade-in">
            <div className="w-12 h-12 mx-auto mb-4 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
              <FileText className="w-6 h-6 text-ink-muted" />
            </div>
            <h2 className="font-display text-xl font-light mb-2">还没有历史记录</h2>
            <p className="text-sm text-ink-soft mb-6">去工作台开始你的第一次协作吧</p>
            <Link to="/workspace" className="btn-gradient inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-medium">
              进入工作台
            </Link>
          </div>
        ) : (
          <>
            <div className="text-xs text-ink-faint mb-4">共 {total} 条记录</div>
            <div className="space-y-3">
              {items.map((item, i) => (
                <div
                  key={item.id}
                  className="glass rounded-2xl overflow-hidden animate-fade-up"
                  style={{ animationDelay: `${i * 0.03}s` }}
                >
                  {/* 卡片头部 */}
                  <div
                    className="p-4 flex items-center gap-4 cursor-pointer"
                    onClick={() => handleExpand(item)}
                  >
                    <div className="w-12 h-12 rounded-md flex items-center justify-center text-lg flex-shrink-0 bg-bg-subtle border border-border">
                      {item.team_icon || item.team_name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm truncate">{item.title || item.team_name}</span>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-ink-faint">
                        <span className="flex items-center gap-1">
                          <Users className="w-3 h-3" /> {item.team_name}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageCircle className="w-3 h-3" /> {item.message_count} 条
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" /> {formatTime(item.created_at)}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(item.id) }}
                      className="w-8 h-8 flex items-center justify-center rounded-full text-ink-faint hover:text-clay hover:bg-clay-soft transition-colors flex-shrink-0"
                      title="删除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    {expandedId === item.id ? (
                      <ChevronDown className="w-4 h-4 text-ink-faint flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-ink-faint flex-shrink-0" />
                    )}
                  </div>

                  {/* 展开详情 */}
                  {expandedId === item.id && (
                    <div className="border-t border-border bg-bg-subtle p-4">
                      {detailLoading ? (
                        <div className="flex items-center justify-center py-6">
                          <Loader2 className="w-4 h-4 animate-spin text-ink-muted" />
                        </div>
                      ) : detail && detail.messages && detail.messages.length > 0 ? (
                        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                          {detail.messages.map((m: any, idx: number) => (
                            <HistoryMessageBubble key={idx} msg={m} />
                          ))}
                        </div>
                      ) : (
                        <div className="text-center text-xs text-ink-faint py-6">暂无消息内容</div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => { const p = Math.max(1, page - 1); setPage(p); load(p) }}
                  disabled={page <= 1}
                  className="px-3 py-1.5 rounded-md glass text-xs disabled:opacity-40 hover:bg-surface-hover transition-colors"
                >
                  上一页
                </button>
                <span className="text-xs text-ink-soft px-3">{page} / {totalPages}</span>
                <button
                  onClick={() => { const p = Math.min(totalPages, page + 1); setPage(p); load(p) }}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 rounded-md glass text-xs disabled:opacity-40 hover:bg-surface-hover transition-colors"
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ===== 历史消息气泡（复用 WorkspacePage 样式） =====

function HistoryMessageBubble({ msg }: { msg: any }) {
  const isUser = msg.role === 'user'
  const isError = msg.role === 'error'

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-up">
        <div className="flex items-start gap-2.5 max-w-[75%]">
          <div className="btn-gradient rounded-2xl rounded-tr-md px-4 py-2.5">
            <p className="msg-content text-sm text-surface">{msg.content}</p>
          </div>
          <div className="w-9 h-9 rounded-full bg-ink flex items-center justify-center text-lg flex-shrink-0">
            {msg.avatar || '我'}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2.5 animate-fade-up">
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center text-lg flex-shrink-0"
        style={{ backgroundColor: (msg.color || '#8C4A57') + '15', border: `2px solid ${(msg.color || '#8C4A57')}30` }}
      >
        {msg.avatar || msg.name.charAt(0).toUpperCase()}
      </div>
      <div className="max-w-[78%] flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium" style={{ color: msg.color || '#8C4A57' }}>{msg.name}</span>
        </div>
        <div className={`rounded-2xl rounded-tl-md px-4 py-2.5 ${isError ? 'bg-clay-soft border border-clay-soft' : 'glass'}`}>
          <p className={`msg-content text-sm ${isError ? 'text-clay' : 'text-ink'}`}>{msg.content}</p>
        </div>
      </div>
    </div>
  )
}

function formatTime(s: string): string {
  try {
    const d = new Date(s)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    const day = 24 * 60 * 60 * 1000
    if (diff < day) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    if (diff < 7 * day) {
      return `${Math.floor(diff / day)} 天前`
    }
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  } catch {
    return s
  }
}
