import { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: (err: Error, reset: () => void) => ReactNode
}

interface State {
  err: Error | null
}

/**
 * 全局 ErrorBoundary — 防止单个组件抛错导致整页空白
 * 显示具体错误信息,方便排查
 */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { err: null }

  static getDerivedStateFromError(err: Error): State {
    return { err }
  }

  componentDidCatch(err: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[AppErrorBoundary] runtime error:', err, info)
  }

  reset = () => {
    this.setState({ err: null })
  }

  render() {
    const { err } = this.state
    if (err) {
      if (this.props.fallback) return this.props.fallback(err, this.reset)
      return (
        <div className="min-h-screen flex items-center justify-center px-6 bg-[#FAF8F5]">
          <div className="max-w-xl w-full rounded-xl border border-[#E5DDD5] bg-white p-8">
            <div className="font-mono text-xs text-[#8C4A57] mb-3">/ RUNTIME ERROR</div>
            <h1 className="font-display text-2xl text-[#0E0E0C] mb-2">页面渲染失败</h1>
            <p className="text-sm text-[#5A5550] mb-4">
              组件运行时抛出了异常,详细信息如下:
            </p>
            <pre className="text-xs bg-[#FAF8F5] border border-[#E5DDD5] rounded-md p-3 overflow-auto max-h-64 text-[#8C4A57] font-mono whitespace-pre-wrap break-all">
              {err.message}
              {'\n\n'}
              {err.stack?.split('\n').slice(0, 8).join('\n')}
            </pre>
            <div className="mt-4 flex gap-2">
              <button
                onClick={this.reset}
                className="px-4 py-2 rounded-md bg-[#0E0E0C] text-white text-sm font-medium hover:bg-[#2A2A28] transition-colors"
              >
                重试
              </button>
              <button
                onClick={() => window.location.href = '/'}
                className="px-4 py-2 rounded-md border border-[#E5DDD5] text-sm font-medium text-[#0E0E0C] hover:bg-[#FAF8F5] transition-colors"
              >
                回首页
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
