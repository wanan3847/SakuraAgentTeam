/**
 * ProvidersPage — LLM 供应商与配置管理
 *
 * 借鉴 hermes-agent 的设计：
 * - 两种模式：从内置厂商选 / 完全自定义端点
 * - 用户自己填 API Key + Base URL + Model（不是共享 key）
 * - 测试连接 / 拉取模型列表
 * - 我的配置管理（保存/切换/删除/设为默认）
 *
 * 借鉴 opendesign 的设计原则：
 * - 统一无图标风格（用首字母色块代替 emoji）
 * - 极简留白，8px 栅格
 * - 60-30-10 色彩比例
 * - 最多 3 种字体
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import SakuraPetals from '../components/SakuraPetals'
import {
  type LLMProvider,
  type UserLLMConfig,
  fetchProviders,
  fetchFreeProviders,
  fetchMyConfigs,
  saveConfig,
  updateConfig,
  deleteConfig,
  fetchModels,
  testConnection,
  testMyConfig,
  refreshMyModels,
} from '../lib/providersApi'

type Tab = 'builtin' | 'custom' | 'mine'

export function ProvidersPage() {
  const { token, isAuthenticated } = useAuth()
  const [tab, setTab] = useState<Tab>('builtin')
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [freeProviders, setFreeProviders] = useState<LLMProvider[]>([])
  const [myConfigs, setMyConfigs] = useState<UserLLMConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'free' | 'cn' | 'intl'>('all')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [all, free] = await Promise.all([fetchProviders(), fetchFreeProviders()])
      setProviders(all || [])
      setFreeProviders(free)
      if (token) {
        const mine = await fetchMyConfigs(token)
        setMyConfigs(mine || [])
      }
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  const filtered = useMemo(() => {
    let list = providers
    if (filter === 'free') list = list.filter((p) => p.free_tier)
    if (filter === 'cn') list = list.filter((p) => p.region === 'cn')
    if (filter === 'intl') list = list.filter((p) => p.region !== 'cn')
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.id.toLowerCase().includes(q) ||
          p.models.some((m) => m.toLowerCase().includes(q)),
      )
    }
    return list
  }, [providers, filter, search])

  return (
    <div className="min-h-screen aurora-bg">
      <SakuraPetals count={3} />
      <div className="relative z-10 max-w-6xl mx-auto px-6 py-10">
        {/* Header */}
        <header className="mb-8">
          <a href="/" className="text-sm text-ink-muted hover:text-ink transition-colors">
            ← 返回首页
          </a>
          <h1 className="font-display text-4xl text-ink mt-3 mb-2">
            LLM 供应商
          </h1>
          <p className="text-ink-soft text-sm leading-relaxed max-w-2xl">
            选择大模型厂商，填入你自己的 API Key 和 Base URL。
            你的配置只属于你自己，不会共享给其他用户。
            支持两种模式：从 254 个内置厂商中选择，或完全自定义端点。
          </p>
        </header>

        {/* 三步上手 — 明确告诉用户怎么用 */}
        <section className="mb-8 p-5 rounded-xl border border-border bg-bg-subtle">
          <div className="text-xs font-mono text-ink-faint mb-3 tracking-widest">/ 上手 3 步</div>
          <ol className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { n: '01', t: '选厂商', d: '从下方 254 个内置厂商中挑一个，或切到「自定义端点」接入 Ollama / vLLM / 本地模型' },
              { n: '02', t: '填 Key', d: '展开卡片，填入你自己的 API Key 和默认 Model。点「测试连接」验证可用' },
              { n: '03', t: '用起来', d: '点「保存为我的配置」→ 勾选默认 → 进入工作台对话即走你配的 Key' },
            ].map((s) => (
              <li key={s.n} className="rounded-lg border border-border bg-surface p-3">
                <div className="font-mono text-xs text-ink-faint mb-1">{s.n}</div>
                <div className="text-sm font-medium text-ink mb-1">{s.t}</div>
                <div className="text-xs text-ink-muted leading-relaxed">{s.d}</div>
              </li>
            ))}
          </ol>
        </section>

        {/* Tabs */}
        <nav className="flex gap-1 mb-8 p-1 bg-bg-subtle glass rounded-xl w-fit">
          {(
            [
              { id: 'builtin', label: '内置厂商', count: providers.length },
              { id: 'custom', label: '自定义端点' },
              { id: 'mine', label: '我的配置', count: myConfigs.length },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t.id
                  ? 'bg-surface text-ink shadow-sm'
                  : 'text-ink-muted hover:text-ink-soft'
              }`}
            >
              {t.label}
              {'count' in t && t.count !== undefined && (
                <span className="ml-1.5 text-xs text-ink-faint">{t.count}</span>
              )}
            </button>
          ))}
        </nav>

        {/* Content */}
        {tab === 'builtin' && (
          <BuiltinProvidersTab
            providers={filtered}
            freeProviders={freeProviders}
            loading={loading}
            search={search}
            setSearch={setSearch}
            filter={filter}
            setFilter={setFilter}
            isAuthenticated={isAuthenticated}
            token={token}
            onSaved={load}
          />
        )}

        {tab === 'custom' && (
          <CustomEndpointTab
            isAuthenticated={isAuthenticated}
            token={token}
            onSaved={load}
          />
        )}

        {tab === 'mine' && (
          <MyConfigsTab
            configs={myConfigs}
            loading={loading}
            isAuthenticated={isAuthenticated}
            token={token}
            onChanged={load}
          />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 统一的首字母色块（代替 emoji 图标）
// ---------------------------------------------------------------------------

function Avatar({ name, size = 'md' }: { name: string; size?: 'sm' | 'md' | 'lg' }) {
  const initial = name.charAt(0).toUpperCase()
  const sizes = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-10 h-10 text-sm',
    lg: 'w-12 h-12 text-base',
  }
  return (
    <div
      className={`${sizes[size]} rounded-lg flex items-center justify-center font-mono font-semibold text-ink-soft bg-bg-subtle border border-border flex-shrink-0`}
    >
      {initial}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 1: 内置厂商列表
// ---------------------------------------------------------------------------

function BuiltinProvidersTab({
  providers,
  freeProviders,
  loading,
  search,
  setSearch,
  filter,
  setFilter,
  isAuthenticated,
  token,
  onSaved,
}: {
  providers: LLMProvider[]
  freeProviders: LLMProvider[]
  loading: boolean
  search: string
  setSearch: (s: string) => void
  filter: 'all' | 'free' | 'cn' | 'intl'
  setFilter: (f: 'all' | 'free' | 'cn' | 'intl') => void
  isAuthenticated: boolean
  token: string | null
  onSaved: () => void
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (loading) {
    return (
      <div className="text-center py-20 text-ink-faint text-sm">加载中…</div>
    )
  }

  return (
    <div>
      {/* 搜索 + 筛选 */}
      <div className="flex flex-wrap gap-3 mb-6">
        <input
          type="search"
          name="provider-search"
          id="provider-search"
          autoComplete="off"
          data-form-type="other"
          data-lpignore="true"
          spellCheck={false}
          placeholder="搜索厂商名 / ID / 模型…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-4 py-2.5 rounded-lg border border-border bg-surface text-sm focus:outline-none focus:border-ink-muted"
        />
        <div className="flex gap-1 p-1 bg-bg-subtle rounded-lg">
          {(
            [
              { id: 'all', label: '全部' },
              { id: 'free', label: '免费额度' },
              { id: 'cn', label: '国内' },
              { id: 'intl', label: '国际' },
            ] as const
          ).map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                filter === f.id
                  ? 'bg-surface text-ink shadow-sm'
                  : 'text-ink-muted hover:text-ink-soft'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* 厂商列表 */}
      {providers.length === 0 ? (
        <div className="text-center py-20 text-ink-faint text-sm">
          没有匹配的厂商
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {(providers || []).map((p) => (
            <ProviderCard
              key={p.id}
              provider={p}
              expanded={expandedId === p.id}
              onToggle={() =>
                setExpandedId(expandedId === p.id ? null : p.id)
              }
              isAuthenticated={isAuthenticated}
              token={token}
              onSaved={onSaved}
            />
          ))}
        </div>
      )}

      {/* 免费额度提示 */}
      {freeProviders.length > 0 && filter !== 'free' && (
        <div className="mt-8 p-4 rounded-lg bg-bg-subtle glass border border-border">
          <p className="text-sm text-ink-soft">
            <span className="font-medium text-ink">
              {freeProviders.length} 个厂商
            </span>
            提供免费额度，适合学习和测试。
            <button
              onClick={() => setFilter('free')}
              className="ml-2 text-ink underline underline-offset-2 hover:text-ink-soft"
            >
              查看免费厂商
            </button>
          </p>
        </div>
      )}
    </div>
  )
}

function ProviderCard({
  provider,
  expanded,
  onToggle,
  isAuthenticated,
  token,
  onSaved,
}: {
  provider: LLMProvider
  expanded: boolean
  onToggle: () => void
  isAuthenticated: boolean
  token: string | null
  onSaved: () => void
}) {
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState(provider.models[0] || '')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [saving, setSaving] = useState(false)

  const handleFetchModels = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetchModels(provider.base_url, apiKey)
      if (res.success && res.models) {
        setTestResult({ ok: true, msg: `发现 ${res.models.length} 个可用模型` })
        if (res.models.length > 0 && !model) {
          setModel(res.models[0])
        }
      } else {
        setTestResult({ ok: false, msg: res.error || '拉取失败' })
      }
    } finally {
      setTesting(false)
    }
  }

  const handleTest = async () => {
    if (!model) {
      setTestResult({ ok: false, msg: '请先选择模型' })
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testConnection(provider.base_url, apiKey, model)
      if (res.success) {
        setTestResult({
          ok: true,
          msg: `连接成功！回复: ${res.reply?.slice(0, 50) || '(空)'}`,
        })
      } else {
        setTestResult({ ok: false, msg: res.error || '测试失败' })
      }
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!token) return
    if (!apiKey) {
      setTestResult({ ok: false, msg: '请填入 API Key' })
      return
    }
    if (!model) {
      setTestResult({ ok: false, msg: '请选择模型' })
      return
    }
    setSaving(true)
    try {
      const res = await saveConfig(token, {
        provider_id: provider.id,
        base_url: provider.base_url,
        api_key: apiKey,
        model,
        models: provider.models,
      })
      if (res.success) {
        setTestResult({ ok: true, msg: '配置已保存到「我的配置」' })
        setApiKey('')
        onSaved()
      } else {
        setTestResult({ ok: false, msg: res.error || '保存失败' })
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={`rounded-xl border bg-surface overflow-hidden transition-all ${
      expanded ? 'border-ink-muted shadow-sm' : 'border-border hover:border-ink-muted cursor-pointer'
    }`}>
      {/* 卡片头部 — 纯文字,不要图标 */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-ink text-sm truncate">
              {provider.name}
            </h3>
            {provider.free_tier && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-sage-soft text-sage border border-sage-soft font-mono">
                免费
              </span>
            )}
            {provider.region === 'cn' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-subtle text-ink-soft border border-border font-mono">
                国内
              </span>
            )}
          </div>
          <p className="text-xs text-ink-muted font-mono mt-0.5 truncate">
            {provider.id} · {provider.models.length} 个模型
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {!expanded && (
            <span className="hidden sm:inline-block text-[10px] font-mono text-ink-faint px-2 py-0.5 rounded border border-border">
              点击配置
            </span>
          )}
          <svg
            className={`w-4 h-4 text-ink-muted transition-transform flex-shrink-0 ${
              expanded ? 'rotate-180 text-ink' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* 展开内容 */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-border pt-4 space-y-3">
          {/* 元数据 */}
          <div className="grid grid-cols-1 gap-2 text-xs">
            <div className="flex items-start gap-2">
              <span className="text-ink-faint font-mono w-20 flex-shrink-0">Base URL</span>
              <code className="text-ink-soft break-all">{provider.base_url}</code>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-ink-faint font-mono w-20 flex-shrink-0">文档</span>
              <a
                href={provider.docs_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sakura-700 hover:underline break-all"
              >
                {provider.docs_url}
              </a>
            </div>
            {provider.free_tier && provider.free_tier_desc && (
              <div className="flex items-start gap-2">
                <span className="text-ink-faint font-mono w-20 flex-shrink-0">免费额度</span>
                <span className="text-ink-soft">{provider.free_tier_desc}</span>
              </div>
            )}
          </div>

          {/* 推荐模型 */}
          {(provider.models || []).length > 0 && (
            <div>
              <p className="text-xs text-ink-faint font-mono mb-1.5">推荐模型</p>
              <div className="flex flex-wrap gap-1.5">
                {(provider.models || []).slice(0, 6).map((m) => (
                  <button
                    key={m}
                    onClick={() => setModel(m)}
                    className={`text-xs px-2 py-1 rounded border font-mono transition-all ${
                      model === m
                        ? 'bg-ink text-surface border-ink'
                        : 'bg-surface text-ink-soft border-border hover:border-ink-muted'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* API Key 输入 */}
          <div>
            <label className="text-xs text-ink-faint font-mono mb-1.5 block">
              你的 API Key
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                name="provider-apikey"
                id="provider-apikey"
                autoComplete="new-password"
                data-form-type="other"
                data-lpignore="true"
                spellCheck={false}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={isAuthenticated ? 'sk-...' : '请先登录'}
                disabled={!isAuthenticated}
                className="flex-1 px-3 py-2 rounded-lg border border-border text-sm font-mono focus:outline-none focus:border-ink-muted disabled:bg-bg-subtle disabled:text-ink-faint"
              />
              <button
                onClick={handleFetchModels}
                disabled={!isAuthenticated || testing}
                className="px-3 py-2 rounded-lg border border-border text-xs text-ink-soft hover:bg-bg-subtle disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {testing ? '拉取中…' : '拉取模型'}
              </button>
            </div>
          </div>

          {/* 模型选择 */}
          <div>
            <label className="text-xs text-ink-faint font-mono mb-1.5 block">
              使用模型
            </label>
            <input
              type="text"
              name="provider-model"
              id="provider-model"
              autoComplete="off"
              data-form-type="other"
              data-lpignore="true"
              spellCheck={false}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="模型名"
              className="w-full px-3 py-2 rounded-lg border border-border text-sm font-mono focus:outline-none focus:border-ink-muted"
            />
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleTest}
              disabled={!isAuthenticated || testing || !apiKey}
              className="flex-1 px-3 py-2 rounded-lg border border-border text-xs text-ink-soft hover:bg-bg-subtle disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {testing ? '测试中…' : '测试连接'}
            </button>
            <button
              onClick={handleSave}
              disabled={!isAuthenticated || saving || !apiKey || !model}
              className="flex-1 px-3 py-2 rounded-lg bg-ink text-surface text-xs hover:bg-ink-soft disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? '保存中…' : '保存到我的配置'}
            </button>
          </div>

          {/* 测试结果 */}
          {testResult && (
            <div
              className={`text-xs p-2.5 rounded-lg font-mono ${
                testResult.ok
                  ? 'bg-sage-soft text-sage border border-sage-soft'
                  : 'bg-clay-soft text-clay border border-clay-soft'
              }`}
            >
              {testResult.ok ? '✓ ' : '✗ '}
              {testResult.msg}
            </div>
          )}

          {!isAuthenticated && (
            <p className="text-xs text-ink-faint text-center">
              <a href="/auth" className="text-ink underline underline-offset-2">
                登录
              </a>
              后可保存配置
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 2: 自定义端点
// ---------------------------------------------------------------------------

function CustomEndpointTab({
  isAuthenticated,
  token,
  onSaved,
}: {
  isAuthenticated: boolean
  token: string | null
  onSaved: () => void
}) {
  const [displayName, setDisplayName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [saving, setSaving] = useState(false)

  const handleFetchModels = async () => {
    if (!baseUrl) {
      setTestResult({ ok: false, msg: '请填入 Base URL' })
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetchModels(baseUrl, apiKey)
      if (res.success && res.models) {
        setAvailableModels(res.models)
        setTestResult({ ok: true, msg: `发现 ${res.models.length} 个可用模型` })
        if (res.models.length > 0 && !model) {
          setModel(res.models[0])
        }
      } else {
        setTestResult({ ok: false, msg: res.error || '拉取失败' })
      }
    } finally {
      setTesting(false)
    }
  }

  const handleTest = async () => {
    if (!baseUrl || !model) {
      setTestResult({ ok: false, msg: '请填入 Base URL 和模型名' })
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testConnection(baseUrl, apiKey, model)
      if (res.success) {
        setTestResult({
          ok: true,
          msg: `连接成功！回复: ${res.reply?.slice(0, 50) || '(空)'}`,
        })
      } else {
        setTestResult({ ok: false, msg: res.error || '测试失败' })
      }
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!token) return
    if (!baseUrl || !model) {
      setTestResult({ ok: false, msg: 'Base URL 和模型名是必填项' })
      return
    }
    setSaving(true)
    try {
      const res = await saveConfig(token, {
        provider_id: 'custom',
        display_name: displayName || '自定义端点',
        base_url: baseUrl,
        api_key: apiKey,
        model,
        models: availableModels,
      })
      if (res.success) {
        setTestResult({ ok: true, msg: '配置已保存' })
        setDisplayName('')
        setBaseUrl('')
        setApiKey('')
        setModel('')
        setAvailableModels([])
        onSaved()
      } else {
        setTestResult({ ok: false, msg: res.error || '保存失败' })
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="rounded-xl border border-border bg-surface p-6 space-y-4">
        <div>
          <h2 className="font-medium text-ink text-lg mb-1">自定义端点</h2>
          <p className="text-sm text-ink-muted">
            适用于 Ollama / vLLM / llama.cpp / LM Studio 等本地部署，
            或任何 OpenAI 兼容的 API 端点。
          </p>
        </div>

        {/* 显示名 */}
        <div>
          <label className="text-xs text-ink-faint font-mono mb-1.5 block">
            配置名称（可选）
          </label>
          <input
            type="text"
            name="llm-display-name"
            id="llm-display-name"
            autoComplete="off"
            data-form-type="other"
            data-lpignore="true"
            spellCheck={false}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="我的本地模型"
            className="w-full px-3 py-2 rounded-lg border border-border text-sm focus:outline-none focus:border-ink-muted"
          />
        </div>

        {/* Base URL */}
        <div>
          <label className="text-xs text-ink-faint font-mono mb-1.5 block">
            Base URL <span className="text-clay">*</span>
          </label>
          <input
            type="text"
            name="llm-base-url"
            id="llm-base-url"
            autoComplete="off"
            data-form-type="other"
            spellCheck={false}
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://localhost:11434/v1"
            className="w-full px-3 py-2 rounded-lg border border-border text-sm font-mono focus:outline-none focus:border-ink-muted"
          />
          <p className="text-xs text-ink-faint mt-1">
            常见格式：http://localhost:11434/v1（Ollama）、http://localhost:8000/v1（vLLM）
          </p>
        </div>

        {/* API Key */}
        <div>
          <label className="text-xs text-ink-faint font-mono mb-1.5 block">
            API Key（可选，本地部署通常不需要）
          </label>
          <input
            type="password"
            name="llm-api-key"
            id="llm-api-key"
            autoComplete="new-password"
            data-form-type="other"
            data-lpignore="true"
            spellCheck={false}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            className="w-full px-3 py-2 rounded-lg border border-border text-sm font-mono focus:outline-none focus:border-ink-muted"
          />
        </div>

        {/* 拉取模型 */}
        <div className="flex gap-2">
          <button
            onClick={handleFetchModels}
            disabled={testing || !baseUrl}
            className="px-4 py-2 rounded-lg border border-border text-sm text-ink-soft hover:bg-bg-subtle disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {testing ? '拉取中…' : '拉取可用模型'}
          </button>
        </div>

        {/* 模型选择 */}
        <div>
          <label className="text-xs text-ink-faint font-mono mb-1.5 block">
            使用模型 <span className="text-clay">*</span>
          </label>
          {availableModels.length > 0 ? (
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border text-sm font-mono focus:outline-none focus:border-ink-muted bg-surface"
            >
              <option value="">选择模型…</option>
              {availableModels.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              name="llm-model-name"
              id="llm-model-name"
              autoComplete="off"
              data-form-type="other"
              data-lpignore="true"
              spellCheck={false}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="手动输入模型名"
              className="w-full px-3 py-2 rounded-lg border border-border text-sm font-mono focus:outline-none focus:border-ink-muted"
            />
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-2 pt-2">
          <button
            onClick={handleTest}
            disabled={testing || !baseUrl || !model}
            className="flex-1 px-4 py-2 rounded-lg border border-border text-sm text-ink-soft hover:bg-bg-subtle disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {testing ? '测试中…' : '测试连接'}
          </button>
          <button
            onClick={handleSave}
            disabled={!isAuthenticated || saving || !baseUrl || !model}
            className="flex-1 px-4 py-2 rounded-lg bg-ink text-surface text-sm hover:bg-ink-soft disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? '保存中…' : '保存配置'}
          </button>
        </div>

        {/* 测试结果 */}
        {testResult && (
          <div
            className={`text-xs p-3 rounded-lg font-mono ${
              testResult.ok
                ? 'bg-sage-soft text-sage border border-sage-soft'
                : 'bg-clay-soft text-clay border border-clay-soft'
            }`}
          >
            {testResult.ok ? '✓ ' : '✗ '}
            {testResult.msg}
          </div>
        )}

        {!isAuthenticated && (
          <p className="text-xs text-ink-faint text-center">
            <a href="/auth" className="text-ink underline underline-offset-2">
              登录
            </a>
            后可保存配置
          </p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 3: 我的配置
// ---------------------------------------------------------------------------

function MyConfigsTab({
  configs,
  loading,
  isAuthenticated,
  token,
  onChanged,
}: {
  configs: UserLLMConfig[]
  loading: boolean
  isAuthenticated: boolean
  token: string | null
  onChanged: () => void
}) {
  if (loading) {
    return <div className="text-center py-20 text-ink-faint text-sm">加载中…</div>
  }

  if (!isAuthenticated) {
    return (
      <div className="text-center py-20">
        <p className="text-ink-muted text-sm mb-3">登录后查看你的配置</p>
        <a
          href="/auth"
          className="inline-block px-4 py-2 rounded-lg bg-ink text-surface text-sm hover:bg-ink-soft"
        >
          去登录
        </a>
      </div>
    )
  }

  if ((configs || []).length === 0) {
    return (
      <div className="text-center py-20">
        <p className="text-ink-muted text-sm mb-2">还没有保存任何配置</p>
        <p className="text-ink-faint text-xs">
          去「内置厂商」或「自定义端点」添加你的第一个配置
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {(configs || []).map((c) => (
        <ConfigCard
          key={c.id}
          config={c}
          token={token!}
          onChanged={onChanged}
        />
      ))}
    </div>
  )
}

function ConfigCard({
  config,
  token,
  onChanged,
}: {
  config: UserLLMConfig
  token: string
  onChanged: () => void
}) {
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState({
    display_name: config.display_name,
    base_url: config.base_url,
    api_key: '',
    model: config.model,
  })

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testMyConfig(token, config.id)
      if (res.success) {
        setTestResult({
          ok: true,
          msg: `连接正常！回复: ${res.reply?.slice(0, 50) || '(空)'}`,
        })
      } else {
        setTestResult({ ok: false, msg: res.error || '测试失败' })
      }
    } finally {
      setTesting(false)
    }
  }

  const handleRefreshModels = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await refreshMyModels(token, config.id)
      if (res.success) {
        setTestResult({
          ok: true,
          msg: `刷新成功，发现 ${res.models?.length || 0} 个模型`,
        })
        onChanged()
      } else {
        setTestResult({ ok: false, msg: res.error || '刷新失败' })
      }
    } finally {
      setTesting(false)
    }
  }

  const handleSetDefault = async () => {
    await updateConfig(token, config.id, { is_default: true })
    onChanged()
  }

  const handleDelete = async () => {
    if (!confirm(`确定删除「${config.display_name}」配置吗？`)) return
    setDeleting(true)
    try {
      await deleteConfig(token, config.id)
      onChanged()
    } finally {
      setDeleting(false)
    }
  }

  const handleSaveEdit = async () => {
    setSaving(true)
    try {
      const payload: any = {
        display_name: editForm.display_name,
        base_url: editForm.base_url,
        model: editForm.model,
      }
      // 只有填了 api_key 才更新(空值不传,保留原 key)
      if (editForm.api_key.trim()) {
        payload.api_key = editForm.api_key.trim()
      }
      const res = await updateConfig(token, config.id, payload)
      if (res.success) {
        setEditing(false)
        setEditForm((f) => ({ ...f, api_key: '' }))
        onChanged()
      } else {
        setTestResult({ ok: false, msg: res.error || '保存失败' })
      }
    } finally {
      setSaving(false)
    }
  }

  const handleCancelEdit = () => {
    setEditing(false)
    setEditForm({
      display_name: config.display_name,
      base_url: config.base_url,
      api_key: '',
      model: config.model,
    })
  }

  return (
    <div
      className={`rounded-xl border border-border bg-surface p-4 transition-all ${
        config.is_default
          ? 'border-ink ring-1 ring-ink'
          : 'border-border hover:border-border-strong'
      }`}
    >
      <div className="flex items-start gap-3">
        <Avatar name={config.display_name} size="lg" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-medium text-ink text-sm">
              {config.display_name}
            </h3>
            {config.is_default && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-ink text-surface font-mono">
                默认
              </span>
            )}
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-subtle text-ink-soft font-mono border border-border">
              {config.provider_id}
            </span>
          </div>
          <p className="text-xs text-ink-muted font-mono mt-1 truncate">
            {config.model}
          </p>
          <p className="text-xs text-ink-faint font-mono mt-0.5 truncate">
            {config.base_url}
          </p>
          <div className="flex items-center gap-3 mt-2 text-xs text-ink-faint">
            <span>{config.models.length} 个模型</span>
            <span>·</span>
            <span>{config.has_api_key ? 'Key 已设置' : '无 Key'}</span>
            {config.updated_at && (
              <>
                <span>·</span>
                <span>{new Date(config.updated_at).toLocaleDateString()}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 编辑表单 */}
      {editing && (
        <div className="mt-3 pt-3 border-t border-border space-y-2">
          <div>
            <label className="text-[10px] text-ink-faint font-mono">显示名</label>
            <input
              type="text"
              value={editForm.display_name}
              onChange={(e) => setEditForm((f) => ({ ...f, display_name: e.target.value }))}
              className="w-full mt-0.5 px-2.5 py-1.5 rounded-lg border border-border bg-bg-subtle text-sm outline-none focus:border-ink"
              autoComplete="off"
              data-form-type="other"
              data-lpignore="true"
            />
          </div>
          <div>
            <label className="text-[10px] text-ink-faint font-mono">Base URL</label>
            <input
              type="text"
              value={editForm.base_url}
              onChange={(e) => setEditForm((f) => ({ ...f, base_url: e.target.value }))}
              className="w-full mt-0.5 px-2.5 py-1.5 rounded-lg border border-border bg-bg-subtle text-sm font-mono outline-none focus:border-ink"
              autoComplete="off"
              data-form-type="other"
              data-lpignore="true"
            />
          </div>
          <div>
            <label className="text-[10px] text-ink-faint font-mono">API Key（留空保留原 Key）</label>
            <input
              type="password"
              value={editForm.api_key}
              onChange={(e) => setEditForm((f) => ({ ...f, api_key: e.target.value }))}
              placeholder="输入新 Key 覆盖,留空则不变"
              className="w-full mt-0.5 px-2.5 py-1.5 rounded-lg border border-border bg-bg-subtle text-sm font-mono outline-none focus:border-ink"
              autoComplete="new-password"
              data-form-type="other"
              data-lpignore="true"
            />
          </div>
          <div>
            <label className="text-[10px] text-ink-faint font-mono">模型</label>
            <input
              type="text"
              value={editForm.model}
              onChange={(e) => setEditForm((f) => ({ ...f, model: e.target.value }))}
              list={`models-${config.id}`}
              className="w-full mt-0.5 px-2.5 py-1.5 rounded-lg border border-border bg-bg-subtle text-sm font-mono outline-none focus:border-ink"
              autoComplete="off"
              data-form-type="other"
              data-lpignore="true"
            />
            <datalist id={`models-${config.id}`}>
              {(config.models || []).map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSaveEdit}
              disabled={saving}
              className="px-3 py-1.5 rounded-lg bg-ink text-surface text-xs hover:bg-ink/90 disabled:opacity-50"
            >
              {saving ? '保存中…' : '保存'}
            </button>
            <button
              onClick={handleCancelEdit}
              className="px-3 py-1.5 rounded-lg border border-border text-xs text-ink-soft hover:bg-bg-subtle"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex gap-2 mt-3 pt-3 border-t border-border">
        <button
          onClick={handleTest}
          disabled={testing}
          className="px-3 py-1.5 rounded-lg border border-border text-xs text-ink-soft hover:bg-bg-subtle disabled:opacity-50"
        >
          {testing ? '测试中…' : '测试连接'}
        </button>
        <button
          onClick={handleRefreshModels}
          disabled={testing}
          className="px-3 py-1.5 rounded-lg border border-border text-xs text-ink-soft hover:bg-bg-subtle disabled:opacity-50"
        >
          刷新模型
        </button>
        <button
          onClick={() => { setEditing(!editing); if (editing) handleCancelEdit() }}
          className="px-3 py-1.5 rounded-lg border border-border text-xs text-ink-soft hover:bg-bg-subtle"
        >
          {editing ? '收起' : '编辑'}
        </button>
        {!config.is_default && (
          <button
            onClick={handleSetDefault}
            className="px-3 py-1.5 rounded-lg border border-border text-xs text-ink-soft hover:bg-bg-subtle"
          >
            设为默认
          </button>
        )}
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="ml-auto px-3 py-1.5 rounded-lg border border-clay-soft text-xs text-clay hover:bg-clay-soft disabled:opacity-50"
        >
          {deleting ? '删除中…' : '删除'}
        </button>
      </div>

      {/* 测试结果 */}
      {testResult && (
        <div
          className={`mt-3 text-xs p-2.5 rounded-lg font-mono ${
            testResult.ok
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {testResult.ok ? '✓ ' : '✗ '}
          {testResult.msg}
        </div>
      )}
    </div>
  )
}
