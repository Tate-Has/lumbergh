import { Routes, Route } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Dashboard from './pages/Dashboard'
import LoginPage from './pages/LoginPage'
import SessionDetail from './pages/SessionDetail'
import TerminalWindow from './pages/TerminalWindow'
import PWAUpdatePrompt from './components/PWAUpdatePrompt'
import AttentionNotifier from './components/AttentionNotifier'
import ErrorBoundary from './components/ErrorBoundary'

function App() {
  const { loading, authenticated } = useAuth()

  if (loading) return null
  if (!authenticated) return <LoginPage />

  return (
    <>
      <ErrorBoundary label="Lumbergh">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/session/:name" element={<SessionDetail />} />
          <Route path="/session/:name/term" element={<TerminalWindow />} />
        </Routes>
      </ErrorBoundary>
      <PWAUpdatePrompt />
      <AttentionNotifier />
    </>
  )
}

export default App
