import { useLocation, useNavigate } from 'react-router-dom'

const TABS = [
  { path: '/', label: 'Sessions' },
  { path: '/focus', label: 'Workspace' },
] as const

interface Props {
  size?: 'default' | 'compact'
}

export default function ViewToggle({ size = 'default' }: Props) {
  const location = useLocation()
  const navigate = useNavigate()

  const inSession = location.pathname.startsWith('/session/')
  const activeIndex = location.pathname.startsWith('/focus') ? 1 : 0

  const compact = size === 'compact'
  const padX = compact ? 'px-3.5' : 'px-5'
  const padY = compact ? 'py-1' : 'py-1.5'
  const text = compact ? 'text-sm' : 'text-sm'

  return (
    <div className="relative grid grid-cols-2 rounded-full p-0.5 shrink-0 border border-border-default">
      {!inSession && (
        <div
          className="absolute top-0.5 bottom-0.5 left-0.5 w-[calc(50%-2px)] rounded-full bg-accent shadow-sm transition-transform duration-200 ease-in-out"
          style={{
            transform: activeIndex === 1 ? 'translateX(calc(100% + 4px))' : 'translateX(0)',
          }}
        />
      )}
      {TABS.map((tab) => {
        const isActive =
          !inSession &&
          (tab.path === '/' ? location.pathname === '/' : location.pathname.startsWith(tab.path))
        return (
          <button
            key={tab.path}
            onClick={() => navigate(tab.path)}
            className={`relative z-10 ${padX} ${padY} text-center rounded-full ${text} font-semibold transition-colors ${
              isActive
                ? 'text-white'
                : inSession
                  ? 'text-text-secondary hover:text-accent hover:bg-control-bg-hover'
                  : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
