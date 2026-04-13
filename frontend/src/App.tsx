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

  if (loading) return null
  if (!authenticated) return <LoginPage />

  const showChrome = !location.pathname.startsWith('/session/')

  return (
    <>
      {showChrome && <TabBar />}
      {showChrome && <AppHeader />}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/focus" element={<FocusWorkspace />} />
        <Route path="/session/:name" element={<SessionDetail />} />
      </Routes>
    </>
  )
}

export default App
