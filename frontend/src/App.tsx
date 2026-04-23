import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Dashboard from './pages/Dashboard'
import FocusWorkspace from './pages/FocusWorkspace'
import LoginPage from './pages/LoginPage'
import SessionDetail from './pages/SessionDetail'
import TabBar from './components/TabBar'
import AppHeader from './components/AppHeader'

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

  const showChrome = !location.pathname.startsWith('/session/')

  return (
    <div className="h-full flex flex-col">
      {showChrome && <TabBar />}
      {showChrome && <AppHeader />}
      <div className="flex-1 min-h-0">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/focus" element={<FocusWorkspace />} />
          <Route path="/session/:name" element={<SessionDetail />} />
        </Routes>
      </div>
    </div>
  )
}

export default App
