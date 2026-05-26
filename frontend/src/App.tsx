import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Dashboard from './pages/Dashboard'
import FocusWorkspace from './pages/FocusWorkspace'
import LoginPage from './pages/LoginPage'
import SessionDetail from './pages/SessionDetail'
import TerminalWindow from './pages/TerminalWindow'
import PWAUpdatePrompt from './components/PWAUpdatePrompt'

function App() {
  const { loading, authenticated } = useAuth()
  const location = useLocation()

  // Track the last non-session view so the back button in sessions
  // always returns to either / or /focus, never another session.
  useEffect(() => {
    if (location.pathname === '/' || location.pathname === '/focus') {
      sessionStorage.setItem('lumbergh:lastView', location.pathname)
    }
  }, [location.pathname])

  if (loading) return null
  if (!authenticated) return <LoginPage />

  return (
    <>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/focus" element={<FocusWorkspace />} />
        <Route path="/session/:name" element={<SessionDetail />} />
        <Route path="/session/:name/term" element={<TerminalWindow />} />
      </Routes>
      <PWAUpdatePrompt />
    </>
  )
}

export default App
