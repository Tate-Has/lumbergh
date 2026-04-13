import { useState, useEffect, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Sun, Moon, Settings, Plus, BookOpen, Zap, Archive } from 'lucide-react'
import { getApiBase } from '../config'
import { useTheme } from '../hooks/useTheme'
import CreateSessionModal from './CreateSessionModal'
import SettingsModal from './SettingsModal'

interface PlanInfo {
  plan: string
  limit: number
  used: number
}

export default function AppHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const { theme, setTheme } = useTheme()
  const isWorkspace = location.pathname.startsWith('/focus')

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showSettingsModal, setShowSettingsModal] = useState(false)
  const [creatingScratch, setCreatingScratch] = useState(false)
  const [planInfo, setPlanInfo] = useState<PlanInfo | null>(null)

  const fetchPlanInfo = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBase()}/cloud/plan`)
      if (res.ok) setPlanInfo(await res.json())
    } catch {
      // Cloud plan info is optional
    }
  }, [])

  useEffect(() => {
    fetchPlanInfo()
    const interval = setInterval(fetchPlanInfo, 30000)
    return () => clearInterval(interval)
  }, [fetchPlanInfo])

  const handleCreateScratch = async () => {
    if (creatingScratch) return
    setCreatingScratch(true)
    try {
      const res = await fetch(`${getApiBase()}/sessions/scratch`, { method: 'POST' })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to create scratch session')
      }
      const data = await res.json()
      navigate(`/session/${data.name}`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create scratch session')
    } finally {
      setCreatingScratch(false)
    }
  }

  const handleSessionCreated = () => {
    window.dispatchEvent(new Event('lumbergh:sessions-changed'))
  }

  return (
    <>
      <header className="flex items-center justify-between px-4 py-2.5 bg-bg-surface border-b border-border-default">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-text-secondary">Lumbergh</h1>
          {planInfo && planInfo.limit > 0 && (
            <span
              className={`text-xs font-medium ${planInfo.used >= planInfo.limit ? 'text-yellow-500' : 'text-text-muted'}`}
            >
              Cloud: {planInfo.used}/{planInfo.limit}
            </span>
          )}
          {planInfo && planInfo.limit === 0 && (
            <span className="text-xs font-medium text-text-muted">Cloud: Pro</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <a
            href="https://voglster.github.io/lumbergh/"
            target="_blank"
            rel="noopener noreferrer"
            title="Documentation"
            className="p-2 text-text-tertiary hover:text-text-primary hover:bg-control-bg rounded transition-colors"
          >
            <BookOpen size={18} />
          </a>
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="p-2 text-text-tertiary hover:text-text-primary hover:bg-control-bg rounded transition-colors"
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <button
            onClick={() => setShowSettingsModal(true)}
            title="Settings"
            data-testid="settings-btn"
            className="p-2 text-text-tertiary hover:text-text-primary hover:bg-control-bg rounded transition-colors"
          >
            <Settings size={18} />
          </button>
          {isWorkspace && (
            <button
              onClick={() => window.dispatchEvent(new Event('lumbergh:open-archive'))}
              title="View archive"
              className="p-2 text-text-tertiary hover:text-text-primary hover:bg-control-bg rounded transition-colors"
            >
              <Archive size={18} />
            </button>
          )}
          <button
            onClick={handleCreateScratch}
            disabled={creatingScratch}
            title="Quick scratch session"
            data-testid="scratch-session-btn"
            className="p-2 text-amber-400 hover:bg-amber-600/20 hover:text-amber-300 disabled:opacity-50 rounded transition-colors"
          >
            <Zap size={16} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            data-testid="new-session-btn"
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 rounded transition-colors"
          >
            <Plus size={16} />
            New Session
          </button>
        </div>
      </header>

      {showCreateModal && (
        <CreateSessionModal
          onClose={() => setShowCreateModal(false)}
          onCreated={handleSessionCreated}
        />
      )}

      {showSettingsModal && <SettingsModal onClose={() => setShowSettingsModal(false)} />}
    </>
  )
}
