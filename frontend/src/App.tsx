import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import HomePage from './pages/HomePage'
import NewTaskPage from './pages/NewTaskPage'
import SessionPage from './pages/SessionPage'
import ProjectsPage from './pages/ProjectsPage'
import ExperiencePage from './pages/ExperiencePage'
import ArtifactsPage from './pages/ArtifactsPage'
import HistoryPage from './pages/HistoryPage'

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100">
      <nav className="bg-white dark:bg-gray-800 shadow border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <Link to="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg" />
              <span className="text-lg font-bold text-gray-800 dark:text-white">SakuraAgentTeam</span>
            </Link>
            <div className="flex items-center gap-3">
              <Link to="/" className="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600">
                首页
              </Link>
              <Link to="/new-task" className="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600">
                新建任务
              </Link>
              <Link to="/projects" className="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600">
                项目历史
              </Link>
              <Link to="/artifacts" className="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600">
                产物浏览
              </Link>
              <Link to="/history" className="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600">
                任务历史
              </Link>
              <Link to="/experiences" className="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600">
                经验库
              </Link>
              <a href="/docs" target="_blank" rel="noopener noreferrer" className="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600">
                API
              </a>
            </div>
          </div>
        </div>
      </nav>
      <main>{children}</main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={
          <Layout>
            <HomePage />
          </Layout>
        } />
        <Route path="/new-task" element={
          <Layout>
            <NewTaskPage />
          </Layout>
        } />
        <Route path="/session" element={
          <Layout>
            <SessionPage />
          </Layout>
        } />
        <Route path="/projects" element={
          <Layout>
            <ProjectsPage />
          </Layout>
        } />
        <Route path="/artifacts" element={
          <Layout>
            <ArtifactsPage />
          </Layout>
        } />
        <Route path="/artifacts/:sessionId" element={
          <Layout>
            <ArtifactsPage />
          </Layout>
        } />
        <Route path="/history" element={
          <Layout>
            <HistoryPage />
          </Layout>
        } />
        <Route path="/experiences" element={
          <Layout>
            <ExperiencePage />
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  )
}

export default App
