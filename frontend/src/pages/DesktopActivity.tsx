import { useTheme } from '../hooks/useTheme'
import TopNav from '../components/TopNav'
import CombinedActivityFeed from '../components/activity/CombinedActivityFeed'

export default function DesktopActivity() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="flex flex-col h-full bg-bg-sunken text-text-primary overflow-hidden">
      <header
        className="glass flex items-center justify-between p-4 border-b border-border-default shrink-0"
        style={{ paddingTop: 'max(1rem, env(safe-area-inset-top))' }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-text-secondary">Lumbergh</h1>
          <TopNav active="desktop" />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="w-8 h-8 rounded-[var(--radius-md)] bg-control-bg hover:bg-control-bg-hover flex items-center justify-center text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-hidden px-4 py-4 pb-20 sm:px-8 sm:py-6 sm:pb-6">
        <CombinedActivityFeed />
      </div>
    </div>
  )
}
