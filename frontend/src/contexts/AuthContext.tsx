import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { login as apiLogin, register as apiRegister, getMe, UserInfo } from '../lib/authApi'

interface AuthContextValue {
  user: UserInfo | null
  token: string | null
  loading: boolean
  isAuthenticated: boolean
  isAdmin: boolean
  login: (username: string, password: string) => Promise<{ success: boolean; message?: string }>
  register: (username: string, email: string, password: string) => Promise<{ success: boolean; message?: string }>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const TOKEN_KEY = 'sakura_token'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // 从 localStorage 恢复登录状态
  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY)
    if (!saved) {
      setLoading(false)
      return
    }
    getMe(saved)
      .then((u) => {
        if (u) {
          setToken(saved)
          setUser(u)
        } else {
          localStorage.removeItem(TOKEN_KEY)
        }
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string) => {
    try {
      const d = await apiLogin(username, password)
      if (d.success && d.token) {
        localStorage.setItem(TOKEN_KEY, d.token)
        setToken(d.token)
        setUser(d.user || null)
        return { success: true }
      }
      return { success: false, message: d.error || d.message || '登录失败' }
    } catch (e: any) {
      return { success: false, message: e.message || '网络错误' }
    }
  }

  const register = async (username: string, email: string, password: string) => {
    try {
      const d = await apiRegister(username, email, password)
      if (d.success && d.token) {
        localStorage.setItem(TOKEN_KEY, d.token)
        setToken(d.token)
        setUser(d.user || null)
        return { success: true }
      }
      return { success: false, message: d.error || d.message || '注册失败' }
    } catch (e: any) {
      return { success: false, message: e.message || '网络错误' }
    }
  }

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }

  const isAdmin = user?.role === 'admin'
  const isAuthenticated = !!user && !!token

  return (
    <AuthContext.Provider value={{ user, token, loading, isAuthenticated, isAdmin, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
