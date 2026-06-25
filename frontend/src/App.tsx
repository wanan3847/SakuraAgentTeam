import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import HomePage from './pages/HomePage'
import AgentLibraryPage from './pages/AgentLibraryPage'
import TeamBuilderPage from './pages/TeamBuilderPage'
import WorkspacePage from './pages/WorkspacePage'
import AuthPage from './pages/AuthPage'
import HistoryPage from './pages/HistoryPage'
import AdminPage from './pages/AdminPage'
import TutorialPage from './pages/TutorialPage'
import AccountPage from './pages/AccountPage'
import { ProvidersPage } from './pages/ProvidersPage'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/agents" element={<AgentLibraryPage />} />
          <Route path="/builder" element={<TeamBuilderPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/tutorial" element={<TutorialPage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/providers" element={<ProvidersPage />} />
          <Route path="*" element={<HomePage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
