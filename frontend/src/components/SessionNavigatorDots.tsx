import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { UserRoundCog } from 'lucide-react'
import { getApiBase } from '../config'
import { useIsDesktop } from '../hooks/useMediaQuery'
import type { SessionBase } from '../utils/sessionStatus'
import {
  getSessionStatus,
  statusColorClasses,
  parseSessionsPayload,
  resolveWorkerParent,
} from '../utils/sessionStatus'
import { navigatorGroups } from '../utils/sessionOrder'

const statusRingClasses: Record<string, string> = {
  gray: 'ring-gray-500/60',
  yellow: 'ring-yellow-400/60',
  green: 'ring-green-500/60',
  red: 'ring-red-500/60',
  purple: 'ring-purple-500/60',
}

interface Props {
  currentSessionName: string
  compact?: boolean
}

/** Bill pinned to the front of the switcher: the manager icon, not initials, and an
 * action-colored ring so he reads as the fleet manager rather than a peer session. */
function BillDot({
  session,
  compact,
  isCurrent,
  routeSuffix,
}: {
  session: SessionBase
  compact: boolean
  isCurrent: boolean
  routeSuffix: string
}) {
  const navigate = useNavigate()
  const size = compact ? (isCurrent ? 'w-6 h-6' : 'w-5 h-5') : 'w-7 h-7'
  const label = `${session.displayName || 'Bill'} — your manager`
  return (
    <div className="group relative shrink-0">
      <button
        onClick={() => navigate(`/session/${session.name}${routeSuffix}`)}
        title={label}
        className={`shrink-0 rounded-full bg-action/20 text-action flex items-center justify-center transition-all ${size} ${
          isCurrent
            ? 'ring-2 ring-action ring-offset-1 ring-offset-[var(--bg-surface)]'
            : 'ring-1 ring-action/40 hover:scale-110'
        }`}
      >
        <UserRoundCog size={compact ? 12 : 14} />
      </button>
      <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-1.5 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity z-50">
        {label}
      </span>
    </div>
  )
}

function initialsFor(label: string) {
  if (label.includes('-')) {
    const parts = label.split('-')
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  const camelMatch = label.match(/^(.).*?([A-Z])/)
  if (camelMatch) {
    return (camelMatch[1] + camelMatch[2]).toUpperCase()
  }
  return label.slice(0, 2).toUpperCase()
}

/** Bubble geometry. A worker's is a notch smaller than the session it belongs to,
 * in both the desktop row and the compact mobile strip. */
function dotSize(isWorker: boolean, compact: boolean, isCurrent: boolean) {
  if (isWorker) {
    if (!compact) return 'w-5.5 h-5.5 text-[11px]'
    return `${isCurrent ? 'w-5 h-5' : 'w-4 h-4'} text-[7px]`
  }
  if (!compact) return 'w-7 h-7 text-sm'
  return `${isCurrent ? 'w-6 h-6' : 'w-5 h-5'} text-[8px]`
}

/** One session bubble. A worker's bubble is smaller and tucked against the right of
 * the session that spawned it; the row bottom-aligns, so the smaller bubble sits on
 * the floor rather than floating mid-row — the shape that reads as "belongs to". */
function SessionDot({
  session,
  parentLabel,
  compact,
  isCurrent,
  isPulsing,
  routeSuffix,
}: {
  session: SessionBase
  parentLabel: string | null
  compact: boolean
  isCurrent: boolean
  isPulsing: boolean
  routeSuffix: string
}) {
  const navigate = useNavigate()
  const status = getSessionStatus(session)
  const colors = statusColorClasses[status.color]
  const isWorker = parentLabel !== null

  const size = dotSize(isWorker, compact, isCurrent)
  const ring = isCurrent
    ? `ring-2 ${session.theOne ? 'ring-blue-400' : statusRingClasses[status.color]} ring-offset-1 ring-offset-[var(--bg-surface)]`
    : `hover:scale-110${session.theOne ? ' ring-1 ring-blue-400/50' : ''}`
  const hug = isWorker ? (compact ? '-ml-0.5' : '-ml-1') : ''

  const tooltipText = isWorker
    ? `${session.displayName || session.name} — ${status.label} · sub-session of ${parentLabel}`
    : `${session.displayName || session.name} — ${status.label}`

  return (
    <div className={`group relative shrink-0 ${hug}`}>
      <button
        onClick={() => navigate(`/session/${session.name}${routeSuffix}`)}
        className={`shrink-0 rounded-full transition-all ${colors.dot} flex items-center justify-center font-bold text-black/60 ${size} ${ring} ${
          isPulsing ? 'animate-[pulse-dot_1.2s_ease-in-out_3]' : ''
        }`}
      >
        {initialsFor(session.displayName || session.name)}
      </button>
      <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-1.5 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity z-50">
        {tooltipText}
      </span>
    </div>
  )
}

export default function SessionNavigatorDots({ currentSessionName, compact = false }: Props) {
  const isDesktop = useIsDesktop()
  const location = useLocation()
  const routeSuffix = location.pathname.endsWith('/term') ? '/term' : ''
  const [sessions, setSessions] = useState<SessionBase[]>([])
  const prevStates = useRef<Record<string, string>>({})
  const [alerting, setAlerting] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const res = await fetch(`${getApiBase()}/sessions`)
        if (!res.ok) return
        const active = parseSessionsPayload(await res.json())
        setSessions(active)

        // Detect transitions away from 'working' to trigger 3-pulse alert
        const newAlerting: Record<string, boolean> = {}
        for (const s of active) {
          const prev = prevStates.current[s.name]
          const curr = s.idleState || 'unknown'
          if (prev === 'working' && curr !== 'working') {
            newAlerting[s.name] = true
          }
          prevStates.current[s.name] = curr
        }
        if (Object.keys(newAlerting).length > 0) {
          setAlerting((a) => ({ ...a, ...newAlerting }))
          // Clear after 3 pulses (~1.5s at 0.5s per pulse)
          setTimeout(() => {
            setAlerting((a) => {
              const next = { ...a }
              for (const name of Object.keys(newAlerting)) {
                delete next[name]
              }
              return next
            })
          }, 1500)
        }
      } catch {
        // Ignore fetch errors
      }
    }

    fetchSessions()
    const interval = setInterval(fetchSessions, 5000)
    return () => clearInterval(interval)
  }, [])

  if (!compact && !isDesktop) return null

  const { bill, starred, rest } = navigatorGroups(sessions)

  // Resolve the tooltip's parent through the same call that placed the bubble, so
  // an adopted worker is never nested beside a session the tooltip declines to name.
  const peers = sessions.filter((s) => s.alive && !s.paused)
  const present = new Set(peers.map((s) => s.name))
  const nestedUnder = (s: SessionBase) => {
    const parent = resolveWorkerParent(s, peers, present)
    if (!parent) return null
    return peers.find((p) => p.name === parent)?.displayName || parent
  }

  const renderDots = (group: SessionBase[]) =>
    group.map((s) => (
      <SessionDot
        key={s.name}
        session={s}
        parentLabel={nestedUnder(s)}
        compact={compact}
        isCurrent={s.name === currentSessionName}
        isPulsing={Boolean(alerting[s.name])}
        routeSuffix={routeSuffix}
      />
    ))

  const billDot = bill ? (
    <BillDot
      session={bill}
      compact={compact}
      isCurrent={bill.name === currentSessionName}
      routeSuffix={routeSuffix}
    />
  ) : null

  return (
    <DotRow
      billDot={billDot}
      starredDots={renderDots(starred)}
      restDots={renderDots(rest)}
      compact={compact}
    />
  )
}

function Separator({ compact }: { compact: boolean }) {
  return (
    <div
      className={`w-0.5 ${compact ? 'h-3.5' : 'h-4'} bg-text-secondary/50 mx-1 shrink-0 self-center rounded-full`}
    />
  )
}

/** Lays out the switcher: Bill first, then starred sessions, then the rest, with a
 * separator between any two non-empty groups. Compact is the mobile tab-bar strip;
 * non-compact is the centered desktop header row. Bubbles sit on a shared floor so
 * the smaller worker bubbles hang below their parent instead of beside its middle. */
function DotRow({
  billDot,
  starredDots,
  restDots,
  compact,
}: {
  billDot: React.ReactNode
  starredDots: React.ReactNode[]
  restDots: React.ReactNode[]
  compact: boolean
}) {
  const showBillSep = Boolean(billDot) && starredDots.length + restDots.length > 0
  const showStarSep = starredDots.length > 0 && restDots.length > 0
  const inner = (
    <>
      {billDot}
      {showBillSep && <Separator compact={compact} />}
      {starredDots}
      {showStarSep && <Separator compact={compact} />}
      {restDots}
    </>
  )
  if (compact) {
    return <div className="flex items-end gap-1 shrink-0">{inner}</div>
  }
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex items-end gap-1.5">{inner}</div>
    </div>
  )
}
