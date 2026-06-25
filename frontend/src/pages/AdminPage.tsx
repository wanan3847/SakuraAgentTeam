import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, Shield, Check, X, Loader2, Clock, User, Tag,
  Target, BookOpen, Sparkles, LogIn, Users, Inbox, Ban, Lock,
} from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import { useAuth } from '../contexts/AuthContext'
import { fetchAllSubmissions, reviewSubmission, AgentSubmission } from '../lib/submissionApi'

type Tab = 'submissions' | 'users'
type StatusFilter = 'pending' | 'approved' | 'rejected' | 'all'

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '待审核', color: '#C4955E', bg: '#F5EDE2' },
  approved: { label: '已通过', color: '#6B8E6B', bg: '#EBF0EB' },
  rejected: { label: '已拒绝', color: '#B56B6B', bg: '#F5EAEA' },
}

export default function AdminPage() {
  const { user, token, isAdmin } = useAuth()
  const [tab, setTab] = useState<Tab>('submissions')
  const [items, setItems] = useState<AgentSubmission[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<StatusFilter>('pending')
  const [reviewingId, setReviewingId] = useState<number | null>(null)
  const [reviewNotes, setReviewNotes] = useState('')
  const [reviewStatus, setReviewStatus] = useState<'approved' | 'rejected'>('approved')
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const data = await fetchAllSubmissions(token)
      setItems(data)
    } catch (e: any) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token && isAdmin) load()
  }, [token, isAdmin])

  const handleReview = async (id: number) => {
    if (!token) return
    setSubmitting(true)
    setError('')
    try {
      await reviewSubmission(token, id, reviewStatus, reviewNotes)
      setItems((prev) => prev.map((it) => it.id === id ? { ...it, status: reviewStatus, admin_notes: reviewNotes } : it))
      setReviewingId(null)
      setReviewNotes('')
    } catch (e: any) {
      setError(e.message || '审核失败')
    } finally {
      setSubmitting(false)
    }
  }

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
          <p className="text-sm text-ink-soft mb-6">管理员面板需要登录后访问</p>
          <Link to="/auth" className="btn-gradient inline-flex items-center gap-2 px-6 py-3 rounded-md font-medium">
            <LogIn className="w-4 h-4" /> 去登录
          </Link>
        </div>
      </div>
    )
  }

  // 非管理员
  if (!isAdmin) {
    return (
      <div className="aurora-bg min-h-screen relative flex items-center justify-center px-4">
        <SakuraPetals count={4} />
        <div className="glass rounded-xl p-10 max-w-md w-full text-center relative z-10 animate-fade-up">
          <div className="w-12 h-12 mx-auto mb-4 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
            <Ban className="w-6 h-6 text-ink-muted" />
          </div>
          <h1 className="font-display text-2xl font-light mb-2">
            <span className="text-ink font-medium">无权限</span>
          </h1>
          <p className="text-sm text-ink-soft mb-6">该面板仅管理员可访问</p>
          <Link to="/workspace" className="btn-gradient inline-flex items-center gap-2 px-6 py-3 rounded-md font-medium">
            返回工作台
          </Link>
        </div>
      </div>
    )
  }

  const filtered = filter === 'all' ? items : items.filter((i) => i.status === filter)
  const counts = {
    pending: items.filter((i) => i.status === 'pending').length,
    approved: items.filter((i) => i.status === 'approved').length,
    rejected: items.filter((i) => i.status === 'rejected').length,
  }

  return (
    <div className="aurora-bg min-h-screen relative">
      <SakuraPetals count={3} />

      {/* 顶栏 */}
      <nav className="sticky top-0 z-50 glass">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-soft hover:text-ink transition-colors">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回</span>
          </Link>
          <h1 className="font-bold text-lg text-ink font-medium flex items-center gap-2">
            <Shield className="w-4 h-4" /> 管理员面板
          </h1>
          <div className="w-16" />
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-8 relative z-10">
        {error && (
          <div className="mb-4 text-xs text-clay bg-clay-soft border border-clay-soft rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {/* Tab 切换 */}
        <div className="flex p-1 bg-bg-subtle rounded-full mb-6 max-w-md">
          <button
            onClick={() => setTab('submissions')}
            className={`flex-1 py-2 rounded-full text-sm font-medium transition-all flex items-center justify-center gap-1.5 ${tab === 'submissions' ? 'btn-gradient' : 'text-ink-soft hover:text-ink'}`}
          >
            <Inbox className="w-3.5 h-3.5" /> Agent 提交审核
            {counts.pending > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${tab === 'submissions' ? 'bg-bg-subtle' : 'bg-amber-soft text-amber'}`}>
                {counts.pending}
              </span>
            )}
          </button>
          <button
            onClick={() => setTab('users')}
            className={`flex-1 py-2 rounded-full text-sm font-medium transition-all flex items-center justify-center gap-1.5 ${tab === 'users' ? 'btn-gradient' : 'text-ink-soft hover:text-ink'}`}
          >
            <Users className="w-3.5 h-3.5" /> 用户管理
          </button>
        </div>

        {tab === 'submissions' ? (
          <>
            {/* 状态筛选 */}
            <div className="flex flex-wrap gap-2 mb-6">
              {(['pending', 'approved', 'rejected', 'all'] as StatusFilter[]).map((s) => {
                const isActive = filter === s
                const label = s === 'all' ? '全部' : STATUS_META[s].label
                const count = s === 'all' ? items.length : counts[s]
                return (
                  <button
                    key={s}
                    onClick={() => setFilter(s)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${isActive ? 'btn-gradient' : 'glass text-ink-soft hover:text-ink'}`}
                  >
                    {label} ({count})
                  </button>
                )
              })}
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="w-6 h-6 animate-spin text-ink-muted" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-20 animate-fade-in">
                <div className="w-12 h-12 mx-auto mb-3 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
                  <Inbox className="w-6 h-6 text-ink-muted" />
                </div>
                <p className="text-sm text-ink-soft">暂无提交记录</p>
              </div>
            ) : (
              <div className="space-y-4">
                {filtered.map((item, i) => (
                  <SubmissionCard
                    key={item.id}
                    item={item}
                    index={i}
                    reviewingId={reviewingId}
                    reviewNotes={reviewNotes}
                    reviewStatus={reviewStatus}
                    submitting={submitting}
                    onReviewClick={() => {
                      setReviewingId(reviewingId === item.id ? null : item.id)
                      setReviewNotes('')
                      setReviewStatus('approved')
                    }}
                    onNotesChange={setReviewNotes}
                    onStatusChange={setReviewStatus}
                    onSubmit={() => handleReview(item.id)}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <UserManagementPanel />
        )}
      </div>
    </div>
  )
}

// ===== 提交卡片 =====

function SubmissionCard({
  item, index, reviewingId, reviewNotes, reviewStatus, submitting,
  onReviewClick, onNotesChange, onStatusChange, onSubmit,
}: {
  item: AgentSubmission
  index: number
  reviewingId: number | null
  reviewNotes: string
  reviewStatus: 'approved' | 'rejected'
  submitting: boolean
  onReviewClick: () => void
  onNotesChange: (v: string) => void
  onStatusChange: (v: 'approved' | 'rejected') => void
  onSubmit: () => void
}) {
  const meta = STATUS_META[item.status] || STATUS_META.pending
  const isReviewing = reviewingId === item.id

  return (
    <div className="glass rounded-2xl p-5 animate-fade-up" style={{ animationDelay: `${index * 0.03}s` }}>
      {/* 头部：提交者 + 状态 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-xs text-ink-faint">
          <User className="w-3.5 h-3.5" />
          <span className="font-medium text-ink-soft">{item.username}</span>
          <span>·</span>
          <Clock className="w-3 h-3" />
          <span>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
        </div>
        <span
          className="text-[10px] px-2 py-0.5 rounded-full font-medium"
          style={{ backgroundColor: meta.bg, color: meta.color }}
        >
          {meta.label}
        </span>
      </div>

      {/* Agent 信息 */}
      <div className="flex items-start gap-4 mb-4">
        <div className="w-12 h-12 rounded-md flex items-center justify-center text-lg flex-shrink-0 bg-bg-subtle border border-border">
          {item.agent_avatar || item.agent_name.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-base">{item.agent_name}</h3>
            <span className="text-[10px] font-mono text-ink-faint">{item.agent_id}</span>
          </div>
          <p className="text-xs text-ink-faint mb-2">{item.agent_role}</p>
          <p className="text-sm text-ink-soft leading-relaxed">{item.agent_tagline}</p>
        </div>
      </div>

      {/* 详细字段 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <InfoBlock icon={<Target className="w-3.5 h-3.5" />} label="目标" content={item.agent_goal} color="#C97B8A" />
        <InfoBlock icon={<Tag className="w-3.5 h-3.5" />} label="分类" content={item.agent_category} color="#6B655C" />
        <div className="md:col-span-2">
          <InfoBlock icon={<BookOpen className="w-3.5 h-3.5" />} label="背景故事" content={item.agent_backstory} color="#8C4A57" />
        </div>
        <div className="md:col-span-2">
          <div className="flex items-center gap-1.5 text-[11px] text-ink-faint mb-1.5">
            <Sparkles className="w-3.5 h-3.5" style={{ color: '#6B8E6B' }} />
            <span>技能</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(item.agent_skills || []).map((s, j) => (
              <span key={j} className="text-[10px] px-2 py-0.5 rounded-full bg-bg-subtle text-sage border border-border">
                {s}
              </span>
            ))}
            {(!item.agent_skills || item.agent_skills.length === 0) && (
              <span className="text-[10px] text-ink-faint">无</span>
            )}
          </div>
        </div>
      </div>

      {/* 管理员备注（已审核时显示） */}
      {item.status !== 'pending' && item.admin_notes && (
        <div className="text-[11px] text-ink-soft bg-bg-subtle rounded-lg px-3 py-2 mb-3">
          <span className="text-ink-faint">审核备注：</span>{item.admin_notes}
        </div>
      )}

      {/* 审核操作 */}
      {item.status === 'pending' && (
        <>
          <button
            onClick={onReviewClick}
            className="w-full text-xs text-sakura-700 hover:text-ink py-2 rounded-lg hover:bg-bg-subtle transition-colors flex items-center justify-center gap-1.5"
          >
            {isReviewing ? <X className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            {isReviewing ? '收起审核' : '开始审核'}
          </button>

          {isReviewing && (
            <div className="mt-3 pt-3 border-t border-border space-y-3 animate-fade-in">
              <div className="flex gap-2">
                <button
                  onClick={() => onStatusChange('approved')}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${reviewStatus === 'approved' ? 'bg-sage text-surface' : 'bg-bg-subtle text-ink-soft border border-border'}`}
                >
                  <Check className="w-3.5 h-3.5" /> 通过
                </button>
                <button
                  onClick={() => onStatusChange('rejected')}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${reviewStatus === 'rejected' ? 'bg-clay text-surface' : 'bg-bg-subtle text-ink-soft border border-border'}`}
                >
                  <X className="w-3.5 h-3.5" /> 拒绝
                </button>
              </div>
              <textarea
                value={reviewNotes}
                onChange={(e) => onNotesChange(e.target.value)}
                placeholder="审核备注（可选）..."
                rows={2}
                className="w-full bg-surface rounded-md px-3 py-2 text-xs border border-border focus:border-ink-muted outline-none resize-none"
              />
              <button
                onClick={onSubmit}
                disabled={submitting}
                className="w-full btn-gradient rounded-lg py-2 text-xs font-medium disabled:opacity-60 flex items-center justify-center gap-1.5"
              >
                {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                确认提交审核
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function InfoBlock({ icon, label, content, color }: { icon: React.ReactNode; label: string; content: string; color: string }) {
  return (
    <div className="bg-bg-subtle rounded-xl p-3">
      <div className="flex items-center gap-1.5 text-[11px] text-ink-faint mb-1.5">
        <span style={{ color }}>{icon}</span>
        <span>{label}</span>
      </div>
      <p className="text-xs text-ink-soft leading-relaxed line-clamp-3">{content || '未填写'}</p>
    </div>
  )
}

// ===== 用户管理面板（占位） =====

function UserManagementPanel() {
  return (
    <div className="glass rounded-2xl p-8 text-center animate-fade-in">
      <div className="w-12 h-12 mx-auto mb-3 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
        <Users className="w-6 h-6 text-ink-muted" />
      </div>
      <h2 className="font-display text-xl font-light mb-2">
        <span className="text-ink font-medium">用户管理</span>
      </h2>
      <p className="text-sm text-ink-soft mb-6 max-w-md mx-auto">
        用户管理功能正在开发中。当前可通过 Agent 提交审核 Tab 管理社区贡献的智能体。
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-w-lg mx-auto">
        <div className="bg-bg-subtle rounded-xl p-4">
          <div className="text-2xl font-display text-ink mb-1">-</div>
          <div className="text-[10px] text-ink-faint">总用户数</div>
        </div>
        <div className="bg-bg-subtle rounded-xl p-4">
          <div className="text-2xl font-display text-ink mb-1">-</div>
          <div className="text-[10px] text-ink-faint">今日新增</div>
        </div>
        <div className="bg-bg-subtle rounded-xl p-4">
          <div className="text-2xl font-display text-ink mb-1">-</div>
          <div className="text-[10px] text-ink-faint">活跃用户</div>
        </div>
      </div>
      <p className="text-[10px] text-ink-faint mt-6">统计接口待后端提供</p>
    </div>
  )
}
