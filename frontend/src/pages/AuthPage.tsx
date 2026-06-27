import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, User, Mail, Lock, CheckCircle2, Home, LayoutDashboard } from 'lucide-react'
import SakuraPetals from '../components/SakuraPetals'
import { useAuth } from '../contexts/AuthContext'

const AVATAR_COLORS = ['#C97B8A', '#6B8E6B', '#C4955E', '#8C4A57', '#6B655C', '#4A4540', '#B56B6B', '#9A5A68']

export default function AuthPage() {
  const nav = useNavigate()
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [avatar, setAvatar] = useState('#C97B8A')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password.trim()) {
      setError('请填写用户名和密码')
      return
    }
    if (mode === 'register' && !email.trim()) {
      setError('请填写邮箱')
      return
    }
    setLoading(true)
    try {
      const res =
        mode === 'login'
          ? await login(username.trim(), password)
          : await register(username.trim(), email.trim(), password)
      if (res.success) {
        setSuccess(true)
      } else {
        setError(res.message || '操作失败')
      }
    } catch (err: any) {
      setError(err.message || '网络错误')
    } finally {
      setLoading(false)
    }
  }

  // 登录/注册成功后的提示页
  if (success) {
    return (
      <div className="aurora-bg min-h-screen relative flex items-center justify-center px-4">
        <SakuraPetals count={8} />
        <div className="glass rounded-xl p-10 max-w-md w-full text-center relative z-10 animate-fade-up">
          <div className="w-12 h-12 mx-auto mb-4 rounded-md bg-sage-soft border border-sage-soft flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6 text-sage" />
          </div>
          <h1 className="font-display text-3xl font-light mb-2">
            <span className="text-ink">{mode === 'login' ? '登录成功' : '注册成功'}</span>
          </h1>
          <p className="text-sm text-ink-soft mb-8">
            {mode === 'login'
              ? '欢迎回来，继续你的协作之旅'
              : '已为你创建账户，开启虚拟团队体验'}
          </p>
          <div className="flex flex-col gap-3">
            <button
              onClick={() => nav('/workspace')}
              className="btn-gradient w-full py-3 rounded-md font-medium flex items-center justify-center gap-2"
            >
              <LayoutDashboard className="w-4 h-4" /> 进入工作台
            </button>
            <button
              onClick={() => nav('/')}
              className="w-full py-3 rounded-md font-medium glass text-ink hover:bg-surface-hover transition-colors flex items-center justify-center gap-2"
            >
              <Home className="w-4 h-4" /> 返回首页
            </button>
          </div>
          <div className="mt-6 flex items-center justify-center gap-1.5 text-[11px] text-ink-faint">
            <CheckCircle2 className="w-3 h-3 text-sage" />
            <span>已自动登录，可随时进入工作台</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="aurora-bg min-h-screen relative flex items-center justify-center px-4">
      <SakuraPetals count={6} />

      {/* 返回 */}
      <Link
        to="/"
        className="absolute top-6 left-6 z-20 flex items-center gap-2 text-ink-soft hover:text-ink transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回首页</span>
      </Link>

      {/* 卡片 */}
      <div className="glass rounded-xl p-8 md:p-10 w-full max-w-md relative z-10 animate-fade-up">
        {/* 标题 */}
        <div className="text-center mb-8">
          <div className="mb-3"><span className="text-2xl">🌸</span></div>
          <h1 className="font-display text-3xl font-light mb-2">
            <span className="text-ink">{mode === 'login' ? '欢迎回来' : '加入我们'}</span>
          </h1>
          <p className="text-xs text-ink-soft">
            {mode === 'login' ? '登录继续你的协作之旅' : '注册开启你的虚拟团队'}
          </p>
        </div>

        {/* Tab 切换 */}
        <div className="flex p-1 bg-bg-subtle rounded-full mb-6">
          <button
            type="button"
            onClick={() => { setMode('login'); setError('') }}
            className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${mode === 'login' ? 'btn-gradient' : 'text-ink-soft hover:text-ink'}`}
          >
            登录
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError('') }}
            className={`flex-1 py-2 rounded-full text-sm font-medium transition-all ${mode === 'register' ? 'btn-gradient' : 'text-ink-soft hover:text-ink'}`}
          >
            注册
          </button>
        </div>

        {/* 表单 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 头像选择器（仅注册） */}
          {mode === 'register' && (
            <div>
              <div className="text-xs text-ink-faint mb-2 font-medium">选择头像颜色</div>
              <div className="grid grid-cols-8 gap-2">
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
            </div>
          )}

          {/* 用户名 */}
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint pointer-events-none" />
            <input
              name="username"
              id="auth-username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="用户名（字母 / 数字 / 下划线）"
              className="w-full bg-surface rounded-md pl-11 pr-4 py-3 text-sm border border-border focus:border-ink-muted outline-none"
            />
          </div>

          {/* 邮箱（仅注册） */}
          {mode === 'register' && (
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint pointer-events-none" />
              <input
                name="email"
                id="auth-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="邮箱"
                className="w-full bg-surface rounded-md pl-11 pr-4 py-3 text-sm border border-border focus:border-ink-muted outline-none"
              />
            </div>
          )}

          {/* 密码 */}
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint pointer-events-none" />
            <input
              name="password"
              id="auth-password"
              type="password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'register' ? '设置密码（至少 6 位）' : '密码'}
              className="w-full bg-surface rounded-md pl-11 pr-4 py-3 text-sm border border-border focus:border-ink-muted outline-none"
            />
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="text-xs text-clay bg-clay-soft border border-clay-soft rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* 提交按钮 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full btn-gradient rounded-md py-3 font-medium flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> 处理中...</>
            ) : (
              <>{mode === 'login' ? '登录' : '注册'}</>
            )}
          </button>
        </form>

      </div>
    </div>
  )
}
