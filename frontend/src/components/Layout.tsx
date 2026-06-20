import { Outlet, Link } from 'react-router-dom'
import { Home, PlusCircle, History } from 'lucide-react'

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow">
        <nav className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <Link to="/" className="flex items-center gap-2">
                <span className="text-xl font-bold text-primary-600">SakuraAgentTeam</span>
              </Link>
            </div>
            <div className="flex items-center gap-4">
              <Link
                to="/"
                className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-700 hover:text-primary-600 dark:text-gray-200"
              >
                <Home className="h-4 w-4" />
                首页
              </Link>
              <Link
                to="/new-task"
                className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-700 hover:text-primary-600 dark:text-gray-200"
              >
                <PlusCircle className="h-4 w-4" />
                新建任务
              </Link>
              <Link
                to="/"
                className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-700 hover:text-primary-600 dark:text-gray-200"
              >
                <History className="h-4 w-4" />
                历史记录
              </Link>
            </div>
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
