import { useLocation, useNavigate } from 'react-router-dom'

const TABS = [
  { path: '/', label: 'Sessions' },
  { path: '/focus', label: 'Workspace' },
] as const

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()

  const activeIndex = location.pathname.startsWith('/focus') ? 1 : 0

  return (
    <div className="flex items-center justify-center px-4 py-2 bg-bg-base border-b border-border-default">
      <div className="relative grid grid-cols-2 bg-bg-surface rounded-md p-0.5">
        {/* Sliding indicator */}
        <div
          className="absolute top-0.5 bottom-0.5 left-0.5 w-[calc(50%-2px)] rounded-md bg-bg-elevated shadow-sm transition-transform duration-200 ease-in-out"
          style={{
            transform: activeIndex === 1 ? 'translateX(calc(100% + 4px))' : 'translateX(0)',
          }}
        />
        {TABS.map((tab) => {
          const isActive =
            tab.path === '/' ? location.pathname === '/' : location.pathname.startsWith(tab.path)
          return (
            <button
              key={tab.path}
              onClick={() => navigate(tab.path)}
              className={`relative z-10 px-5 py-1.5 text-center rounded-md text-sm font-medium transition-colors ${
                isActive ? 'text-text-primary' : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
