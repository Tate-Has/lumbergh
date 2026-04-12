import { useLocation, useNavigate } from 'react-router-dom'

const TABS = [
  { path: '/', label: 'Sessions' },
  { path: '/focus', label: 'Focus' },
] as const

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div className="flex items-center gap-1 px-4 py-2 bg-bg-base border-b border-border-default">
      {TABS.map((tab) => {
        const isActive =
          tab.path === '/' ? location.pathname === '/' : location.pathname.startsWith(tab.path)
        return (
          <button
            key={tab.path}
            onClick={() => navigate(tab.path)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              isActive
                ? 'bg-bg-elevated text-text-primary'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-surface'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
