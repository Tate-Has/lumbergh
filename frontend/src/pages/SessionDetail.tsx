import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Settings, PanelRightClose, PanelRightOpen, AlertTriangle } from 'lucide-react'
import { getApiBase } from '../config'
import GlassPanel from '../components/ui/GlassPanel'
import Button from '../components/ui/Button'
import Terminal from '../components/Terminal'
import FileBrowser from '../components/FileBrowser'
import ResizablePanes from '../components/ResizablePanes'
import VerticalResizablePanes from '../components/VerticalResizablePanes'
import TodoList from '../components/TodoList'
import Scratchpad from '../components/Scratchpad'
import PromptTemplates from '../components/PromptTemplates'
import SharedFiles from '../components/SharedFiles'
import TelemetryOptIn from '../components/TelemetryOptIn'
import SessionSummaryOverlay from '../components/SessionSummaryBanner'
import ScratchPromoteBanner from '../components/ScratchPromoteBanner'
import { isSummaryDismissed, dismissSummary, enableSummary } from '../hooks/useSessionSummary'
import GitTab from '../components/graph/GitTab'
import SessionNavigatorDots from '../components/SessionNavigatorDots'
import { useIsDesktop } from '../hooks/useMediaQuery'

type RightPanel = 'git' | 'files' | 'todos' | 'prompts' | 'shared'
type MobileTab = 'terminal' | 'git' | 'files' | 'todos' | 'prompts' | 'shared'

type DiffData = {
  files: Array<{ path: string; diff: string }>
  stats: { additions: number; deletions: number }
}

type TabVisibility = Record<string, boolean>

const ALL_TABS: { id: RightPanel; label: string }[] = [
  { id: 'git', label: 'Git' },
  { id: 'files', label: 'Files' },
  { id: 'todos', label: 'Todo' },
  { id: 'prompts', label: 'Prompts' },
  { id: 'shared', label: 'Shared' },
]

const DEFAULT_TAB_VISIBILITY: TabVisibility = {
  git: true,
  files: true,
  todos: true,
  prompts: true,
  shared: true,
}

// Compare diff data to avoid unnecessary re-renders
type ExistenceState =
  | { status: 'ok' }
  | { status: 'notfound' }
  | { status: 'workdir-missing'; workdir: string }

function useSessionExistence(name: string | undefined): ExistenceState {
  const [state, setState] = useState<ExistenceState>({ status: 'ok' })
  useEffect(() => {
    if (!name) return
    let cancelled = false
    fetch(`${getApiBase()}/sessions/${name}/touch`, { method: 'POST' })
      .then(async (res) => {
        if (cancelled) return
        if (res.status === 404) {
          setState({ status: 'notfound' })
          return
        }
        if (res.status === 410) {
          try {
            const data = await res.json()
            const detail = data?.detail
            if (detail?.code === 'workdir_missing') {
              setState({ status: 'workdir-missing', workdir: detail.workdir || '' })
              return
            }
          } catch {
            // fall through
          }
          setState({ status: 'workdir-missing', workdir: '' })
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [name])
  return state
}

function NotFoundScreen({ sessionName, onBack }: { sessionName: string; onBack: () => void }) {
  const [countdown, setCountdown] = useState(5)
  useEffect(() => {
    if (countdown <= 0) {
      onBack()
      return
    }
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown, onBack])
  return (
    <div className="h-full flex flex-col items-center justify-center bg-bg-sunken text-text-primary gap-4 px-4">
      <GlassPanel variant="elevated" padding="lg" radius="2xl" className="max-w-md w-full">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertTriangle size={32} className="text-danger" />
          <div className="text-text-primary text-lg font-semibold">Session not found</div>
          <p className="text-text-tertiary text-sm">
            The session{' '}
            <span className="text-text-secondary font-mono">&quot;{sessionName}&quot;</span> does
            not exist or has been deleted.
          </p>
          <Button variant="primary" size="md" onClick={onBack}>
            Go to dashboard
          </Button>
          <p className="text-text-muted text-xs">Redirecting in {countdown}s…</p>
        </div>
      </GlassPanel>
    </div>
  )
}

function WorkdirMissingScreen({
  sessionName,
  workdir,
  onBack,
}: {
  sessionName: string
  workdir: string
  onBack: () => void
}) {
  const [deleting, setDeleting] = useState(false)
  const onCleanup = async () => {
    if (!sessionName || deleting) return
    setDeleting(true)
    try {
      const res = await fetch(`${getApiBase()}/sessions/${sessionName}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to delete session')
      }
      onBack()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete session')
      setDeleting(false)
    }
  }
  return (
    <div className="h-full flex flex-col items-center justify-center bg-bg-sunken text-text-primary gap-4 px-4">
      <GlassPanel variant="elevated" padding="lg" radius="2xl" className="max-w-lg w-full">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertTriangle size={32} className="text-warning" />
          <div className="text-text-primary text-lg font-semibold">Working directory missing</div>
          <p className="text-text-tertiary text-sm">
            The session{' '}
            <span className="text-text-secondary font-mono">&quot;{sessionName}&quot;</span> points
            to a directory that no longer exists:
          </p>
          {workdir && (
            <div className="w-full">
              <code className="block text-left text-text-secondary text-xs font-mono bg-bg-sunken/60 border border-border-default rounded-[var(--radius-md)] px-3 py-2 break-all">
                {workdir}
              </code>
            </div>
          )}
          <p className="text-text-muted text-xs">
            This usually happens when a git worktree is removed outside Lumbergh. The session can no
            longer be opened — you can clean it up below.
          </p>
          <div className="flex gap-2 pt-1">
            <Button variant="secondary" size="md" onClick={onBack}>
              Back to dashboard
            </Button>
            <Button variant="danger" size="md" onClick={onCleanup} disabled={deleting}>
              {deleting ? 'Deleting…' : 'Delete session'}
            </Button>
          </div>
        </div>
      </GlassPanel>
    </div>
  )
}

function renderExistenceGuard(
  existence: ExistenceState,
  sessionName: string | undefined,
  onBack: () => void
) {
  const safeName = sessionName ?? ''
  if (existence.status === 'workdir-missing') {
    return (
      <WorkdirMissingScreen sessionName={safeName} workdir={existence.workdir} onBack={onBack} />
    )
  }
  if (existence.status === 'notfound') {
    return <NotFoundScreen sessionName={safeName} onBack={onBack} />
  }
  return null
}

function diffDataEquals(a: DiffData | null, b: DiffData | null): boolean {
  if (a === b) return true
  if (!a || !b) return false
  if (a.stats.additions !== b.stats.additions || a.stats.deletions !== b.stats.deletions) {
    return false
  }
  if (a.files.length !== b.files.length) return false
  for (let i = 0; i < a.files.length; i++) {
    if (a.files[i].path !== b.files[i].path || a.files[i].diff !== b.files[i].diff) {
      return false
    }
  }
  return true
}

export default function SessionDetail() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const isDesktop = useIsDesktop()

  const existence = useSessionExistence(name)

  const [rightPanel, setRightPanel] = useState<RightPanel>(() => {
    const saved = localStorage.getItem('lumbergh:rightPanel')
    if (
      saved === 'git' ||
      saved === 'files' ||
      saved === 'todos' ||
      saved === 'prompts' ||
      saved === 'shared'
    ) {
      return saved
    }
    // Migrate old 'diff' or 'graph' to 'git'
    if (saved === 'diff' || saved === 'graph') return 'git'
    return 'git'
  })
  const [sharedRefreshTrigger, setSharedRefreshTrigger] = useState(0)
  const [gitTabResetTrigger, setGitTabResetTrigger] = useState(0)
  const [mobileTab, setMobileTab] = useState<MobileTab>('terminal')
  const [diffData, setDiffData] = useState<DiffData | null>(null)
  const [showTelemetryOptIn, setShowTelemetryOptIn] = useState(false)
  const [showSessionDots, setShowSessionDots] = useState(true)
  const [globalTabVisibility, setGlobalTabVisibility] =
    useState<TabVisibility>(DEFAULT_TAB_VISIBILITY)
  const [sessionTabVisibility, setSessionTabVisibility] = useState<TabVisibility | null>(null)
  const [showTabSettings, setShowTabSettings] = useState(false)
  const [showSummary, setShowSummary] = useState(false)
  const [isScratch, setIsScratch] = useState(false)
  const tabSettingsRef = useRef<HTMLDivElement>(null)
  const focusFnRef = useRef<(() => void) | null>(null)

  // Fetch settings (telemetry consent + tab visibility)
  useEffect(() => {
    fetch(`${getApiBase()}/settings`)
      .then((res) => res.json())
      .then((data) => {
        if (data.telemetryConsent == null) setShowTelemetryOptIn(true)
        if (data.tabVisibility) setGlobalTabVisibility(data.tabVisibility)
        if (data.showSessionDots != null) setShowSessionDots(data.showSessionDots)
      })
      .catch(() => {})
  }, [])

  // Fetch session metadata for per-session tab visibility + summary auto-show
  useEffect(() => {
    if (!name) return
    fetch(`${getApiBase()}/sessions`)
      .then((res) => res.json())
      .then((data) => {
        const session = (data.sessions || []).find((s: { name: string }) => s.name === name)
        if (session) {
          setSessionTabVisibility(session.tabVisibility || null)
          setIsScratch(session.type === 'scratch')
          // Auto-show summary if: not dismissed, active session, untouched for 30+ min
          if (!isSummaryDismissed() && session.alive && !session.paused) {
            const STALE_MINUTES = 30
            const lastUsed = session.lastUsedAt ? new Date(session.lastUsedAt).getTime() : 0
            const minutesSinceTouch = (Date.now() - lastUsed) / 60_000
            if (minutesSinceTouch >= STALE_MINUTES) {
              setShowSummary(true)
            }
          }
        }
      })
      .catch(() => {})
  }, [name])

  // Persist right panel selection
  useEffect(() => {
    localStorage.setItem('lumbergh:rightPanel', rightPanel)
  }, [rightPanel])

  // Compute effective tab visibility (session overrides global)
  const effectiveTabVisibility = useMemo<TabVisibility>(
    () =>
      sessionTabVisibility
        ? { ...globalTabVisibility, ...sessionTabVisibility }
        : globalTabVisibility,
    [globalTabVisibility, sessionTabVisibility]
  )

  const visibleTabs = useMemo(
    () => ALL_TABS.filter((t) => effectiveTabVisibility[t.id] !== false),
    [effectiveTabVisibility]
  )

  const visibleMobileTabs = useMemo(
    () =>
      [{ id: 'terminal' as MobileTab, label: 'Terminal' }].concat(
        ALL_TABS.filter((t) => effectiveTabVisibility[t.id] !== false)
      ),
    [effectiveTabVisibility]
  )

  const isTerminalOnly = visibleTabs.length === 0

  // Auto-select first visible tab if current is hidden
  useEffect(() => {
    if (visibleTabs.length > 0 && effectiveTabVisibility[rightPanel] === false) {
      setRightPanel(visibleTabs[0].id)
    }
  }, [effectiveTabVisibility, rightPanel, visibleTabs])

  useEffect(() => {
    if (mobileTab !== 'terminal' && effectiveTabVisibility[mobileTab] === false) {
      setMobileTab('terminal')
    }
  }, [effectiveTabVisibility, mobileTab])

  // Close tab settings popover on outside click
  useEffect(() => {
    if (!showTabSettings) return
    const handleClick = (e: MouseEvent) => {
      if (tabSettingsRef.current && !tabSettingsRef.current.contains(e.target as Node)) {
        setShowTabSettings(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showTabSettings])

  // Save per-session tab visibility
  const saveSessionTabVisibility = useCallback(
    async (tv: TabVisibility) => {
      if (!name) return
      setSessionTabVisibility(tv)
      try {
        await fetch(`${getApiBase()}/sessions/${name}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tabVisibility: tv }),
        })
      } catch (err) {
        console.error('Failed to save tab visibility:', err)
      }
    },
    [name]
  )

  const saveShowSessionDots = useCallback(async (value: boolean) => {
    setShowSessionDots(value)
    try {
      await fetch(`${getApiBase()}/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ showSessionDots: value }),
      })
    } catch (err) {
      console.error('Failed to save session dots setting:', err)
    }
  }, [])

  const handleDismissSummary = useCallback(() => {
    dismissSummary()
    setShowSummary(false)
  }, [])

  const handleTempHideSummary = useCallback(() => {
    setShowSummary(false)
  }, [])

  const handleShowSummary = useCallback(() => {
    enableSummary()
    setShowSummary(true)
  }, [])

  const handleFocusReady = useCallback((fn: () => void) => {
    focusFnRef.current = fn
  }, [])

  const handleFocusTerminal = useCallback(() => {
    focusFnRef.current?.()
  }, [])

  const handleSwitchToTerminal = useCallback(() => {
    setMobileTab('terminal')
    focusFnRef.current?.()
  }, [])

  const handleJumpToTodos = useCallback(() => {
    if (effectiveTabVisibility['todos'] === false) return
    setRightPanel('todos')
    setMobileTab('todos')
  }, [effectiveTabVisibility])

  const handleTodoSent = useCallback(
    async (text: string) => {
      if (!name) return
      try {
        await fetch(`${getApiBase()}/sessions/${name}/status-summary`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        })
      } catch (err) {
        console.error('Failed to update status summary:', err)
      }
    },
    [name]
  )

  const handleCycleSession = useCallback(
    async (direction: 'next' | 'prev') => {
      try {
        const res = await fetch(`${getApiBase()}/sessions`)
        if (!res.ok) return
        const data = await res.json()
        const active = (data.sessions || [])
          .filter((s: { alive: boolean; paused?: boolean }) => s.alive && !s.paused)
          .sort((a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name))
        if (active.length <= 1) return
        const currentIdx = active.findIndex((s: { name: string }) => s.name === name)

        // On forward cycle, check starred sessions first — visit the first idle one
        if (direction === 'next') {
          const starredIdle = active.filter(
            (s: { name: string; theOne?: boolean; idleState?: string }) =>
              s.theOne && s.name !== name && s.idleState === 'idle'
          )
          if (starredIdle.length > 0) {
            navigate(`/session/${starredIdle[0].name}`)
            return
          }
        }

        const step = direction === 'next' ? 1 : active.length - 1
        const nextIdx = (currentIdx + step) % active.length
        navigate(`/session/${active[nextIdx].name}`)
      } catch {
        // Ignore errors
      }
    },
    [name, navigate]
  )

  // Ctrl+Shift+J (next) / Ctrl+Shift+K (prev) to cycle sessions.
  // Replaces Ctrl+[ / Ctrl+] which collided with terminal control codes.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && !e.altKey && !e.metaKey) {
        const k = e.key.toLowerCase()
        if (k === 'j' || k === 'k') {
          e.preventDefault()
          handleCycleSession(k === 'j' ? 'next' : 'prev')
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleCycleSession])

  const handleBack = useCallback(() => {
    navigate(sessionStorage.getItem('lumbergh:lastView') || '/')
  }, [navigate])

  const handleReset = useCallback(async () => {
    if (!name) return
    try {
      const res = await fetch(`${getApiBase()}/sessions/${name}/reset`, {
        method: 'POST',
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to reset session')
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to reset session')
    }
  }, [name])

  const diffEtagRef = useRef<string>('')

  const fetchDiffData = useCallback(
    async ({ force = false }: { force?: boolean } = {}) => {
      if (!name) return
      try {
        const headers: Record<string, string> = {}
        if (!force && diffEtagRef.current) headers['If-None-Match'] = diffEtagRef.current
        if (force) {
          // Invalidate backend cache so we get a fresh computation
          await fetch(`${getApiBase()}/sessions/${name}/git/invalidate`, { method: 'POST' }).catch(
            () => {}
          )
        }
        const res = await fetch(`${getApiBase()}/sessions/${name}/git/diff`, { headers })
        if (res.status === 304) return
        const data = await res.json()
        diffEtagRef.current = res.headers.get('etag') || ''
        // Only update state if data actually changed to prevent scroll resets
        setDiffData((prev) => (diffDataEquals(prev, data) ? prev : data))
      } catch (err) {
        console.error('Failed to fetch diff data:', err)
      }
    },
    [name]
  )

  // Lightweight stats for tab badges (polled always)
  const [diffStats, setDiffStats] = useState<{
    files: number
    additions: number
    deletions: number
  } | null>(null)

  // Is the git tab currently visible? (need to poll full diff data when visible)
  const isDiffVisible = isDesktop ? rightPanel === 'git' : mobileTab === 'git'

  // Poll lightweight diff-stats every 10s (for badge counts)
  const statsEtagRef = useRef<string>('')
  useEffect(() => {
    if (!name) return
    const fetchStats = async () => {
      try {
        const headers: Record<string, string> = {}
        if (statsEtagRef.current) headers['If-None-Match'] = statsEtagRef.current
        const res = await fetch(`${getApiBase()}/sessions/${name}/git/diff-stats`, {
          headers,
        })
        if (res.status === 304) return
        statsEtagRef.current = res.headers.get('etag') || ''
        const data = await res.json()
        setDiffStats((prev) => {
          if (
            prev &&
            prev.files === data.files &&
            prev.additions === data.additions &&
            prev.deletions === data.deletions
          ) {
            return prev
          }
          return data
        })
      } catch {
        // ignore
      }
    }
    fetchStats()
    const interval = setInterval(fetchStats, 10000)
    return () => clearInterval(interval)
  }, [name])

  // Full diff: fetch when diff tab becomes visible + poll while visible
  useEffect(() => {
    if (!isDiffVisible) return
    fetchDiffData()
    const interval = setInterval(fetchDiffData, 5000)
    return () => clearInterval(interval)
  }, [isDiffVisible, fetchDiffData])

  // Global paste handler for image uploads
  useEffect(() => {
    const handlePaste = async (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return

      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (!file) continue

          const formData = new FormData()
          formData.append('file', file)

          try {
            const res = await fetch(`${getApiBase()}/shared/upload`, {
              method: 'POST',
              body: formData,
            })
            if (res.ok) {
              // Trigger refresh and switch to shared tab
              setSharedRefreshTrigger((n) => n + 1)
              setRightPanel('shared')
              setMobileTab('shared')
            }
          } catch (err) {
            console.error('Failed to upload image:', err)
          }
          break
        }
      }
    }

    document.addEventListener('paste', handlePaste)
    return () => document.removeEventListener('paste', handlePaste)
  }, [])

  // mobileTabs is now computed as visibleMobileTabs above

  const renderTerminal = () => (
    <div className="h-full relative" data-testid="terminal-container">
      {name ? (
        <Terminal
          sessionName={name}
          onFocusReady={handleFocusReady}
          onBack={isDesktop ? handleBack : undefined}
          onReset={handleReset}
          onCycleSession={handleCycleSession}
          showSessionDots={showSessionDots}
          isVisible={isDesktop || mobileTab === 'terminal'}
          showSummary={showSummary}
          onShowSummary={handleShowSummary}
        />
      ) : (
        <div className="flex items-center justify-center h-full text-text-muted">
          No session selected
        </div>
      )}
      {showSummary && name && (
        <SessionSummaryOverlay
          sessionName={name}
          onDismiss={handleDismissSummary}
          onTempHide={handleTempHideSummary}
        />
      )}
    </div>
  )

  const renderRightPanel = () => (
    <div className="h-full flex flex-col">
      {/* Panel switcher */}
      <div className="flex gap-1 p-2 bg-bg-surface border-b border-border-default">
        <button
          data-testid="tab-collapse"
          onClick={() => {
            const currentVis = sessionTabVisibility || globalTabVisibility
            const allOff = Object.fromEntries(Object.keys(currentVis).map((k) => [k, false]))
            saveSessionTabVisibility(allOff)
          }}
          className="px-2 py-1 rounded text-text-tertiary hover:text-text-secondary hover:bg-control-bg-hover transition-colors"
          title="Collapse side panel"
        >
          <PanelRightClose size={14} />
        </button>
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            data-testid={`tab-${tab.id === 'todos' ? 'todo' : tab.id}`}
            onClick={() => {
              setRightPanel(tab.id)
              if (tab.id === 'git') setGitTabResetTrigger((n) => n + 1)
            }}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              rightPanel === tab.id
                ? 'bg-control-bg-hover text-text-primary'
                : 'bg-control-bg text-text-tertiary hover:bg-control-bg-hover hover:text-text-secondary'
            }`}
          >
            {tab.label}
            {tab.id === 'git' && diffStats && diffStats.files > 0 && (
              <span className="ml-2 text-xs">
                ({diffStats.files})<span className="text-success ml-1">+{diffStats.additions}</span>
                <span className="text-danger ml-1">-{diffStats.deletions}</span>
              </span>
            )}
          </button>
        ))}
        {/* Gear icon for tab visibility settings */}
        <div className="relative ml-auto" ref={tabSettingsRef}>
          <button
            onClick={() => setShowTabSettings((v) => !v)}
            className="px-2 py-1 rounded text-text-tertiary hover:text-text-secondary hover:bg-control-bg-hover transition-colors"
            title="Configure visible tabs"
          >
            <Settings size={14} />
          </button>
          {showTabSettings && (
            <div className="absolute right-0 top-full mt-1 bg-bg-surface border border-border-default rounded-[var(--radius-xl)] shadow-lg p-3 z-50 min-w-[160px]">
              <p className="text-xs text-text-tertiary mb-2 font-medium">Visible Tabs</p>
              <label className="flex items-center gap-2 py-1 text-sm border-b border-border-default mb-1 pb-2">
                <input
                  type="checkbox"
                  checked={isTerminalOnly}
                  onChange={() => {
                    const currentVis = sessionTabVisibility || globalTabVisibility
                    if (isTerminalOnly) {
                      // Restore: use global defaults
                      saveSessionTabVisibility({ ...globalTabVisibility })
                    } else {
                      // Set all to false
                      const allOff = Object.fromEntries(
                        Object.keys(currentVis).map((k) => [k, false])
                      )
                      saveSessionTabVisibility(allOff)
                    }
                  }}
                  className="rounded border-input-border bg-input-bg"
                />
                <span className="text-text-secondary font-medium">Terminal Only</span>
              </label>
              {ALL_TABS.map((tab) => {
                const currentVis = sessionTabVisibility || globalTabVisibility
                const isEnabled = currentVis[tab.id] !== false
                return (
                  <label key={tab.id} className="flex items-center gap-2 py-1 text-sm">
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      onChange={() => {
                        const updated = { ...currentVis, [tab.id]: !isEnabled }
                        saveSessionTabVisibility(updated)
                      }}
                      className="rounded border-input-border bg-input-bg"
                    />
                    <span className="text-text-secondary">{tab.label}</span>
                  </label>
                )
              })}
              <label className="flex items-center gap-2 py-1 text-sm border-t border-border-default mt-1 pt-2">
                <input
                  type="checkbox"
                  checked={showSessionDots}
                  onChange={() => saveShowSessionDots(!showSessionDots)}
                  className="rounded border-input-border bg-input-bg"
                />
                <span className="text-text-secondary">Session Dots</span>
              </label>
            </div>
          )}
        </div>
      </div>
      {/* Panel content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {rightPanel === 'git' && (
          <GitTab
            key={name}
            sessionName={name}
            diffData={diffData}
            onRefreshDiff={() => fetchDiffData({ force: true })}
            onJumpToTodos={handleJumpToTodos}
            onFocusTerminal={handleFocusTerminal}
            resetTrigger={gitTabResetTrigger}
          />
        )}
        {rightPanel === 'files' && (
          <FileBrowser sessionName={name} onFocusTerminal={handleFocusTerminal} />
        )}
        {rightPanel === 'todos' && name && (
          <VerticalResizablePanes
            top={
              <TodoList
                sessionName={name}
                onFocusTerminal={handleFocusTerminal}
                onTodoSent={handleTodoSent}
                onSwitchToTerminal={handleSwitchToTerminal}
              />
            }
            bottom={<Scratchpad sessionName={name} onFocusTerminal={handleFocusTerminal} />}
            defaultTopHeight={50}
            minTopHeight={20}
            maxTopHeight={80}
            storageKey="lumbergh:todoSplitHeight"
          />
        )}
        {rightPanel === 'prompts' && (
          <PromptTemplates sessionName={name} onFocusTerminal={handleFocusTerminal} />
        )}
        {rightPanel === 'shared' && (
          <SharedFiles
            sessionName={name}
            onFocusTerminal={handleFocusTerminal}
            refreshTrigger={sharedRefreshTrigger}
          />
        )}
      </div>
    </div>
  )

  const guard = renderExistenceGuard(existence, name, () => navigate('/'))
  if (guard) return guard

  return (
    <div
      className="h-full flex flex-col bg-bg-sunken text-text-primary"
      style={{ paddingTop: 'env(safe-area-inset-top)' }}
    >
      <ScratchPromoteBanner
        sessionName={name!}
        isScratch={isScratch}
        onPromoted={() => setIsScratch(false)}
      />
      {showTelemetryOptIn && <TelemetryOptIn onClose={() => setShowTelemetryOptIn(false)} />}

      {/* Conditionally render only desktop OR mobile layout (not both) */}
      {isDesktop ? (
        <main className="flex-1 min-h-0">
          {isTerminalOnly ? (
            <div className="h-full relative">
              {renderTerminal()}
              <button
                data-testid="tab-expand"
                onClick={() => saveSessionTabVisibility({ ...globalTabVisibility })}
                className="absolute top-2 right-2 p-1.5 rounded bg-bg-surface/80 border border-border-default text-text-tertiary hover:text-text-primary transition-colors backdrop-blur-sm"
                title="Show side panels"
              >
                <PanelRightOpen size={14} />
              </button>
            </div>
          ) : (
            <ResizablePanes
              left={renderTerminal()}
              right={renderRightPanel()}
              defaultLeftWidth={50}
              minLeftWidth={25}
              maxLeftWidth={75}
              storageKey="lumbergh:mainSplitWidth"
            />
          )}
        </main>
      ) : (
        <div className="flex-1 min-h-0 flex flex-col">
          {/* Tab navigation with back button */}
          <div className="flex gap-1 px-2 py-1 bg-bg-surface border-b border-border-default overflow-x-auto scrollbar-hide">
            {/* Back button */}
            <button
              onClick={() => navigate(sessionStorage.getItem('lumbergh:lastView') || '/')}
              className="shrink-0 px-2 py-1.5 text-text-tertiary hover:text-text-primary transition-colors"
              title="Back"
            >
              <ArrowLeft size={16} />
            </button>
            {/* Separator */}
            <div className="w-px shrink-0 bg-border-default my-1" />
            {showSessionDots && name && (
              <>
                <SessionNavigatorDots compact currentSessionName={name} />
                <div className="w-px shrink-0 bg-border-default my-1" />
              </>
            )}
            {visibleMobileTabs.map((tab) => (
              <button
                key={tab.id}
                data-testid={`tab-${tab.id === 'todos' ? 'todo' : tab.id}`}
                onClick={() => {
                  setMobileTab(tab.id)
                  if (tab.id === 'git') setGitTabResetTrigger((n) => n + 1)
                }}
                className={`shrink-0 px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                  mobileTab === tab.id
                    ? 'bg-control-bg-hover text-text-primary'
                    : 'bg-control-bg text-text-tertiary hover:bg-control-bg-hover hover:text-text-secondary'
                }`}
              >
                {tab.label}
                {tab.id === 'git' && diffStats && diffStats.files > 0 && (
                  <span className="ml-1 text-xs">
                    ({diffStats.files})
                    <span className="text-success ml-1">+{diffStats.additions}</span>
                    <span className="text-danger ml-1">-{diffStats.deletions}</span>
                  </span>
                )}
              </button>
            ))}
          </div>
          {/* Tab content */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {/* Terminal stays mounted to preserve WebSocket connection and buffer */}
            <div className={`h-full ${mobileTab === 'terminal' ? '' : 'hidden'}`}>
              {renderTerminal()}
            </div>
            {mobileTab === 'git' && (
              <GitTab
                sessionName={name}
                diffData={diffData}
                onRefreshDiff={() => fetchDiffData({ force: true })}
                onJumpToTodos={handleJumpToTodos}
                onFocusTerminal={handleFocusTerminal}
                resetTrigger={gitTabResetTrigger}
              />
            )}
            {mobileTab === 'files' && (
              <FileBrowser sessionName={name} onFocusTerminal={handleFocusTerminal} />
            )}
            {mobileTab === 'todos' && name && (
              <VerticalResizablePanes
                top={
                  <TodoList
                    sessionName={name}
                    onFocusTerminal={handleFocusTerminal}
                    onTodoSent={handleTodoSent}
                    onSwitchToTerminal={handleSwitchToTerminal}
                  />
                }
                bottom={<Scratchpad sessionName={name} onFocusTerminal={handleFocusTerminal} />}
                defaultTopHeight={50}
                minTopHeight={20}
                maxTopHeight={80}
                storageKey="lumbergh:todoSplitHeight"
              />
            )}
            {mobileTab === 'prompts' && (
              <PromptTemplates sessionName={name} onFocusTerminal={handleFocusTerminal} />
            )}
            {mobileTab === 'shared' && (
              <SharedFiles
                sessionName={name}
                onFocusTerminal={handleFocusTerminal}
                refreshTrigger={sharedRefreshTrigger}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
