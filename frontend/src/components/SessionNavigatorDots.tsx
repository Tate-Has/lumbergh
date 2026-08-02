import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { UserRoundCog } from 'lucide-react'
import { getApiBase } from '../config'
import { useIsDesktop } from '../hooks/useMediaQuery'
import type { SessionBase } from '../utils/sessionStatus'
import { getSessionStatus, statusColorClasses } from '../utils/sessionStatus'

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

export default function SessionNavigatorDots({ currentSessionName, compact = false }: Props) {
  const isDesktop = useIsDesktop()
  const navigate = useNavigate()
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
        const data = await res.json()
        const active = (data.sessions || [])
          .filter((s: SessionBase) => s.alive && !s.paused)
          .sort((a: SessionBase, b: SessionBase) => a.name.localeCompare(b.name))
        setSessions(active)

        // Detect transitions away from 'working' to trigger 3-pulse alert
        const newAlerting: Record<string, boolean> = {}
        for (const s of active as SessionBase[]) {
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

  const getInitial = (label: string) => {
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

  const billSession = sessions.find((s) => s.name === 'bill')
  const billDot = billSession ? (
    <BillDot
      session={billSession}
      compact={compact}
      isCurrent={billSession.name === currentSessionName}
      routeSuffix={routeSuffix}
    />
  ) : null

  const dots = sessions
    .filter((s) => s.name !== 'bill')
    .map((s) => {
      const status = getSessionStatus(s)
      const colors = statusColorClasses[status.color]
      const isCurrent = s.name === currentSessionName
      const isPulsing = alerting[s.name]

      const tooltipText = `${s.displayName || s.name} — ${status.label}`

      if (compact) {
        return (
          <div key={s.name} className="group relative shrink-0">
            <button
              onClick={() => navigate(`/session/${s.name}${routeSuffix}`)}
              className={`shrink-0 rounded-full transition-all ${colors.dot} flex items-center justify-center font-bold text-black/60 text-[8px] ${
                isCurrent
                  ? `w-6 h-6 ring-2 ${s.theOne ? 'ring-blue-400' : statusRingClasses[status.color]} ring-offset-1 ring-offset-[var(--bg-surface)]`
                  : `w-5 h-5 hover:scale-110${s.theOne ? ' ring-1 ring-blue-400/50' : ''}`
              } ${isPulsing ? 'animate-[pulse-dot_1.2s_ease-in-out_3]' : ''}`}
            >
              {getInitial(s.displayName || s.name)}
            </button>
            <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-1.5 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity z-50">
              {tooltipText}
            </span>
          </div>
        )
      }

      return (
        <div key={s.name} className="group relative">
          <button
            onClick={() => navigate(`/session/${s.name}${routeSuffix}`)}
            className={`rounded-full transition-all ${colors.dot} flex items-center justify-center font-bold text-black/60 ${
              isCurrent
                ? `w-7 h-7 text-sm ring-2 ${s.theOne ? 'ring-blue-400' : statusRingClasses[status.color]} ring-offset-1 ring-offset-[var(--bg-surface)]`
                : `w-7 h-7 text-sm hover:scale-110${s.theOne ? ' ring-1 ring-blue-400/50' : ''}`
            } ${isPulsing ? 'animate-[pulse-dot_1.2s_ease-in-out_3]' : ''}`}
          >
            {getInitial(s.displayName || s.name)}
          </button>
          <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-1.5 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity z-50">
            {tooltipText}
          </span>
        </div>
      )
    })

  const starredNames = new Set(sessions.filter((s) => s.theOne).map((s) => s.name))
  const starredDots = dots.filter((d) => starredNames.has(d.key as string))
  const restDots = dots.filter((d) => !starredNames.has(d.key as string))

  return (
    <DotRow billDot={billDot} starredDots={starredDots} restDots={restDots} compact={compact} />
  )
}

function Separator({ compact }: { compact: boolean }) {
  return (
    <div
      className={`w-0.5 ${compact ? 'h-3.5' : 'h-4'} bg-text-secondary/50 mx-1 shrink-0 rounded-full`}
    />
  )
}

/** Lays out the switcher: Bill first, then starred sessions, then the rest, with a
 * separator between any two non-empty groups. Compact is the mobile tab-bar strip;
 * non-compact is the centered desktop header row. */
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
    return <div className="flex items-center gap-1 shrink-0">{inner}</div>
  }
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex items-center gap-1.5">{inner}</div>
    </div>
  )
}
