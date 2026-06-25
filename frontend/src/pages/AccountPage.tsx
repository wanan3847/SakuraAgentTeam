import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, Mail, Lock, User, Shield, Calendar, Loader2, CheckCircle2,
  LogIn, Sparkles, MessageSquare, Inbox, UserCircle,
} from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import { useAuth } from '../contexts/AuthContext'
import { updateMe, changePassword, fetchMyStats, UserInfo } from '../lib/authApi'

const AVATAR_COLORS = ['#C97B8A', '#6B8E6B', '#C4955E', '#8C4A57', '#6B655C', '#4A4540', '#B56B6B', '#9A5A68']

export default function AccountPage() {
  const { user, token, isAuthenticated, logout } = useAuth()

  const [avatar, setAvatar] = useState(user?.avatar || '#C97B8A')
  const [email, setEmail] = useState(user?.email || '')
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')

  const [savingAvatar, setSavingAvatar] = useState(false)
  const [savingEmail, setSavingEmail] = useState(false)
  const [savingPwd, setSavingPwd] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [stats, setStats] = useState<{ conversations?: number; submissions?: number; [k: string]: any }>({})

  useEffect(() => {
    if (user) {
      setAvatar(user.avatar || '#C97B8A')
      setEmail(user.email || '')
    }
  }, [user])

  useEffect(() => {
    if (token) {
      fetchMyStats(token).then(setStats).catch(() => {})
    }
  }, [token])

  // 未登录
  if (!isAuthenticated || !user || !token) {
    return (
      <div className="aurora-bg min-h-screen relative flex items-center justify-center px-4">
        <SakuraPetals count={4} />
        <div className="glass rounded-xl p-10 max-w-md w-full text-center relative z-10 animate-fade-up">
          <div className="w-12 h-12 mx-auto mb-4 rounded-md bg-bg-subtle border border-border flex items-center justify-center">
            <Lock className="w-6 h-6 text-ink-muted" />
          </div>
          <h1 className="font-display text-2xl font-light mb-2">
            <span className="text-ink">请先登录</span>
          </h1>
          <p className="text-sm text-ink-soft mb-6">账户管理需要登录后访问</p>
          <Link to="/auth" className="btn-gradient inline-flex items-center gap-2 px-6 py-3 rounded-md font-medium">
            <LogIn className="w-4 h-4" /> 去登录
          </Link>
        </div>
      </div>
    )
  }

  const handleSaveAvatar = async () => {
    setSavingAvatar(true)
    setMsg(null)
    try {
      const r = await updateMe(token, { avatar })
      if (r.success) {
        setMsg({ type: 'success', text: '头像已更新' })
      } else {
        setMsg({ type: 'error', text: r.message || r.error || '保存失败' })
      }
    } catch (e: any) {
      setMsg({ type: 'error', text: e.message || '网络错误' })
    } finally {
      setSavingAvatar(false)
    }
  }

  const handleSaveEmail = async () => {
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setMsg({ type: 'error', text: '请输入有效的邮箱地址' })
      return
    }
    setSavingEmail(true)
    setMsg(null)
    try {
      const r = await updateMe(token, { email: email.trim() })
      if (r.success) {
        setMsg({ type: 'success', text: '邮箱已更新' })
      } else {
        setMsg({ type: 'error', text: r.message || r.error || '保存失败' })
      }
    } catch (e: any) {
      setMsg({ type: 'error', text: e.message || '网络错误' })
    } finally {
      setSavingEmail(false)
    }
  }

  const handleChangePwd = async () => {
    if (!oldPwd || !newPwd || !confirmPwd) {
      setMsg({ type: 'error', text: '请填写所有密码字段' })
      return
    }
    if (newPwd.length < 6) {
      setMsg({ type: 'error', text: '新密码至少 6 位' })
      return
    }
    if (newPwd !== confirmPwd) {
      setMsg({ type: 'error', text: '两次输入的新密码不一致' })
      return
    }
    setSavingPwd(true)
    setMsg(null)
    try {
      const r = await changePassword(token, oldPwd, newPwd)
      if (r.success) {
        setMsg({ type: 'success', text: '密码已更新，下次登录请使用新密码' })
        setOldPwd(''); setNewPwd(''); setConfirmPwd('')
      } else {
        setMsg({ type: 'error', text: r.message || r.error || '修改失败' })
      }
    } catch (e: any) {
      setMsg({ type: 'error', text: e.message || '网络错误' })
    } finally {
      setSavingPwd(false)
    }
  }

  return (
    <div className="aurora-bg min-h-screen relative">
      <SakuraPetals count={4} />

      {/* 顶栏 */}
      <nav className="sticky top-0 z-50 glass">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-soft hover:text-ink transition-colors">
            <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回</span>
          </Link>
          <h1 className="font-bold text-lg text-ink">账户管理</h1>
          <div className="w-16" />
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-8 relative z-10 space-y-6">
        {/* 全局消息 */}
        {msg && (
          <div
            className={`text-xs rounded-lg px-3 py-2 flex items-center gap-2 animate-fade-in ${
              msg.type === 'success'
                ? 'bg-sage-soft text-sage border border-sage-soft'
                : 'bg-clay-soft text-clay border border-clay-soft'
            }`}
          >
            {msg.type === 'success' ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
            {msg.text}
          </div>
        )}

        {/* 用户信息卡片 */}
        <UserCard user={user} />

        {/* 使用统计 */}
        <StatsCard stats={stats} />

        {/* 修改头像 */}
        <div className="glass rounded-xl p-6 animate-fade-up">
          <SectionHeader icon={<Sparkles className="w-4 h-4" />} title="修改头像" desc="选择一个颜色作为你的头像标识" />
          <div className="grid grid-cols-8 gap-2 mt-4">
            {AVATAR_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setAvatar(c)}
                className={`w-9 h-9 rounded-md transition-all ${avatar === c ? 'selected-ring' : 'border border-border'}`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <div className="mt-4 flex items-center gap-3">
            <div className="text-xs text-ink-faint">当前：</div>
            <div className="w-10 h-10 rounded-md flex items-center justify-center text-surface flex-shrink-0" style={{ backgroundColor: avatar }}>
              <UserCircle className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <button
              onClick={handleSaveAvatar}
              disabled={savingAvatar || avatar === user.avatar}
              className="btn-gradient ml-auto px-5 py-2 rounded-md text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {savingAvatar ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              保存头像
            </button>
          </div>
        </div>

        {/* 修改邮箱 */}
        <div className="glass rounded-xl p-6 animate-fade-up">
          <SectionHeader icon={<Mail className="w-4 h-4" />} title="修改邮箱" desc="用于接收通知和找回密码" />
          <div className="mt-4 relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
            <input
              name="account-email"
              id="account-email"
              type="email"
              autoComplete="email"
              data-form-type="other"
              spellCheck={false}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-surface rounded-md pl-11 pr-4 py-3 text-sm border border-border focus:border-ink-muted outline-none"
            />
          </div>
          <div className="mt-4 flex justify-end">
            <button
              onClick={handleSaveEmail}
              disabled={savingEmail || email.trim() === user.email}
              className="btn-gradient px-5 py-2 rounded-md text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {savingEmail ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              保存邮箱
            </button>
          </div>
        </div>

        {/* 修改密码 */}
        <div className="glass rounded-xl p-6 animate-fade-up">
          <SectionHeader icon={<Lock className="w-4 h-4" />} title="修改密码" desc="建议定期更换密码以保证账户安全" />
          <div className="space-y-3 mt-4">
            <PwdInput placeholder="旧密码" value={oldPwd} onChange={setOldPwd} />
            <PwdInput placeholder="新密码（至少 6 位）" value={newPwd} onChange={setNewPwd} />
            <PwdInput placeholder="确认新密码" value={confirmPwd} onChange={setConfirmPwd} />
          </div>
          <div className="mt-4 flex justify-end">
            <button
              onClick={handleChangePwd}
              disabled={savingPwd}
              className="btn-gradient px-5 py-2 rounded-md text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {savingPwd ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              更新密码
            </button>
          </div>
        </div>

        {/* 登出 */}
        <div className="glass rounded-xl p-6 flex items-center justify-between animate-fade-up">
          <div>
            <div className="font-medium text-sm">登出当前账户</div>
            <div className="text-xs text-ink-faint mt-1">退出登录后需要重新输入账号密码</div>
          </div>
          <Link
            to="/"
            onClick={logout}
            className="px-5 py-2 rounded-md text-xs font-medium bg-clay-soft text-clay hover:bg-clay-soft transition-colors flex items-center gap-1.5"
          >
            <LogIn className="w-3.5 h-3.5" /> 登出
          </Link>
        </div>
      </div>
    </div>
  )
}

// ===== 子组件 =====

function SectionHeader({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-9 h-9 rounded-xl bg-bg-subtle text-ink-muted flex items-center justify-center flex-shrink-0">
        {icon}
      </div>
      <div>
        <h2 className="font-display text-lg font-light">{title}</h2>
        <p className="text-xs text-ink-faint mt-0.5">{desc}</p>
      </div>
    </div>
  )
}

function PwdInput({ placeholder, value, onChange }: { placeholder: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="relative">
      <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-surface rounded-md pl-11 pr-4 py-3 text-sm border border-border focus:border-ink-muted outline-none"
      />
    </div>
  )
}

function UserCard({ user }: { user: UserInfo }) {
  const roleLabel = user.role === 'admin' ? '管理员' : '普通用户'
  const roleColor = user.role === 'admin' ? '#8C4A57' : '#6B655C'
  return (
    <div className="glass rounded-xl p-6 animate-fade-up">
      <div className="flex items-center gap-4">
        <div className="w-20 h-20 rounded-2xl flex items-center justify-center text-3xl font-mono font-semibold text-surface flex-shrink-0" style={{ backgroundColor: user.avatar || '#C97B8A' }}>
          {user.username.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h2 className="font-display text-2xl text-ink truncate">{user.username}</h2>
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-medium flex items-center gap-1"
              style={{ backgroundColor: roleColor + '15', color: roleColor }}
            >
              <Shield className="w-2.5 h-2.5" /> {roleLabel}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-ink-faint mb-1">
            <Mail className="w-3 h-3" /> <span className="truncate">{user.email || '未设置'}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-ink-faint">
            <Calendar className="w-3 h-3" />
            <span>注册于 {new Date(user.created_at).toLocaleDateString('zh-CN')}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatsCard({ stats }: { stats: { conversations?: number; submissions?: number; [k: string]: any } }) {
  const items = [
    { icon: <MessageSquare className="w-4 h-4" />, label: '对话数', value: stats.conversations ?? '-', color: '#C97B8A' },
    { icon: <Inbox className="w-4 h-4" />, label: '提交数', value: stats.submissions ?? '-', color: '#6B655C' },
  ]
  return (
    <div className="glass rounded-xl p-6 animate-fade-up">
      <SectionHeader icon={<Sparkles className="w-4 h-4" />} title="使用统计" desc="你的活动数据" />
      <div className="grid grid-cols-2 gap-3 mt-4">
        {items.map((it, i) => (
          <div key={i} className="bg-bg-subtle rounded-md p-4 border border-border">
            <div className="flex items-center gap-1.5 text-[11px] text-ink-faint mb-2">
              <span style={{ color: it.color }}>{it.icon}</span>
              <span>{it.label}</span>
            </div>
            <div className="font-display text-2xl text-ink">{it.value}</div>
          </div>
        ))}
      </div>
      {Object.keys(stats).length === 0 && (
        <div className="mt-3 text-[10px] text-ink-faint">统计接口待后端提供</div>
      )}
    </div>
  )
}
