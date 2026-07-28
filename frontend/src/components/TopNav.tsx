import { useNavigate } from 'react-router-dom'
import { LayoutGrid, KanbanSquare, Activity } from 'lucide-react'

export type TopNavView = 'sessions' | 'workspace' | 'desktop'

interface NavItem {
  key: TopNavView
  label: string
  path: string
  icon: typeof LayoutGrid
}

const NAV_ITEMS: NavItem[] = [
  { key: 'sessions', label: 'Sessions', path: '/', icon: LayoutGrid },
  { key: 'workspace', label: 'Workspace', path: '/focus', icon: KanbanSquare },
  { key: 'desktop', label: 'Desktop', path: '/desktop', icon: Activity },
]

interface PlanInfo {
  plan: string
  limit: number
  used: number
}

interface TopNavProps {
  active: TopNavView
  /** Optional Dashboard-only cloud plan badge, rendered after the pill nav. */
  planInfo?: PlanInfo | null
}

export default function TopNav({ active, planInfo }: TopNavProps) {
  const navigate = useNavigate()

  return (
    <>
      {/* Desktop / tablet pill nav */}
      <nav className="hidden sm:flex items-center gap-0.5 rounded-full p-0.5 border border-border-default">
        {NAV_ITEMS.map((item) => {
          const isActive = item.key === active
          return (
            <button
              key={item.key}
              onClick={() => !isActive && navigate(item.path)}
              className={
                isActive
                  ? 'px-3 py-1 text-xs font-semibold rounded-full bg-action text-white'
                  : 'px-3 py-1 text-xs font-semibold rounded-full text-text-secondary hover:text-text-primary transition-colors cursor-pointer'
              }
              aria-current={isActive ? 'page' : undefined}
            >
              {item.label}
            </button>
          )
        })}
      </nav>
      {planInfo && planInfo.limit > 0 && (
        <span
          className={`hidden sm:inline text-xs font-medium ${planInfo.used >= planInfo.limit ? 'text-warning' : 'text-text-muted'}`}
        >
          Cloud: {planInfo.used}/{planInfo.limit}
        </span>
      )}
      {planInfo && planInfo.limit === 0 && (
        <span className="hidden sm:inline text-xs font-medium text-text-muted">Cloud: Pro</span>
      )}

      {/* Mobile bottom tab bar — fixed, safe-area aware, only below `sm`.
          Fixed content height (54px) + safe-area padding. Other fixed mobile
          bars (e.g. Focus Workspace's MobileActionBar) stack above this one
          using the same 54px + env(safe-area-inset-bottom) offset — see
          index.css `.focus-view .mobile-action-bar`. */}
      <nav
        className="sm:hidden fixed bottom-0 left-0 right-0 z-[95] flex items-stretch gap-1 border-t border-border-default bg-bg-elevated px-2 pt-1.5 box-border"
        style={{ height: 'calc(54px + env(safe-area-inset-bottom))' }}
      >
        {NAV_ITEMS.map((item) => {
          const isActive = item.key === active
          const Icon = item.icon
          return (
            <button
              key={item.key}
              onClick={() => !isActive && navigate(item.path)}
              aria-current={isActive ? 'page' : undefined}
              className={`flex-1 flex flex-col items-center justify-center gap-0.5 rounded-[var(--radius-md)] py-1.5 text-[0.7rem] font-semibold transition-colors cursor-pointer ${
                isActive
                  ? 'text-action'
                  : 'text-text-tertiary hover:text-text-primary active:text-text-primary'
              }`}
            >
              <Icon size={18} />
              {item.label}
            </button>
          )
        })}
      </nav>
    </>
  )
}
