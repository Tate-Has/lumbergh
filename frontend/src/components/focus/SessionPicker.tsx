import { useState, useEffect, useRef } from 'react'
import { Plus } from 'lucide-react'
import { getApiBase } from '../../config'
import { getSessionStatus, statusColorClasses, type SessionBase } from '../../utils/sessionStatus'
import { useClickOutside } from '../../hooks/useClickOutside'

interface PickerSession extends SessionBase {
  workdir: string | null
}

interface SessionPickerProps {
  isOpen: boolean
  onClose: () => void
  linkedSessionNames: string[]
  onLinkSession: (sessionName: string) => void
  onCreateNew: () => void
}

export default function SessionPicker({
  isOpen,
  onClose,
  linkedSessionNames,
  onLinkSession,
  onCreateNew,
}: SessionPickerProps) {
  const [sessions, setSessions] = useState<PickerSession[]>([])
  const [loading, setLoading] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useClickOutside(containerRef, isOpen, onClose)

  /* eslint-disable react-hooks/set-state-in-effect -- intentional: fetch sessions when picker opens; setLoading(true) synchronously primes loading state before async chain resolves */
  useEffect(() => {
    if (!isOpen) return
    setLoading(true)
    fetch(`${getApiBase()}/sessions`)
      .then((res) => res.json())
      .then((data) => {
        const raw: PickerSession[] = data.sessions || data || []
        setSessions(raw)
      })
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))
  }, [isOpen])
  /* eslint-enable react-hooks/set-state-in-effect */

  const visibleSessions = sessions.filter(
    (s) => s.alive && !s.paused && !linkedSessionNames.includes(s.name)
  )

  const workdirBasename = (workdir: string | null): string | null => {
    if (!workdir) return null
    const parts = workdir.replace(/\\/g, '/').split('/')
    return parts[parts.length - 1] || null
  }

  if (!isOpen) return null

  return (
    <div className="session-picker fixed inset-0 z-[99] flex items-start justify-center">
      {/* Overlay backdrop */}
      <div className="absolute inset-0 bg-black/40" />

      {/* Floating panel */}
      <div
        ref={containerRef}
        className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-sm bg-bg-elevated border border-border-default rounded-xl shadow-modal z-[100] overflow-hidden"
      >
        {/* Header */}
        <div className="px-3 py-2.5 border-b border-border-default">
          <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">
            Link a session
          </p>
        </div>

        {/* Session list */}
        <div className="max-h-60 overflow-y-auto">
          {loading ? (
            <div className="px-3 py-3 text-sm text-text-tertiary">Loading...</div>
          ) : visibleSessions.length === 0 ? (
            <div className="px-3 py-3 text-sm text-text-tertiary">No active sessions</div>
          ) : (
            visibleSessions.map((session) => {
              const status = getSessionStatus(session)
              const dotClass = statusColorClasses[status.color]?.dot ?? 'bg-gray-500'
              const basename = workdirBasename(session.workdir)

              return (
                <div
                  key={session.name}
                  className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer hover:bg-bg-surface transition-colors duration-100"
                  onClick={() => onLinkSession(session.name)}
                >
                  {/* Status dot */}
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${dotClass}${status.pulse ? ' animate-pulse' : ''}`}
                  />

                  {/* Session info */}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-mono text-text-primary truncate">
                      {session.displayName || session.name}
                    </div>
                    {basename && <div className="text-xs text-text-muted truncate">{basename}</div>}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Create new row */}
        <div className="border-t border-border-default">
          <div
            className="flex items-center gap-2 px-3 py-2.5 cursor-pointer hover:bg-bg-surface transition-colors duration-100"
            onClick={onCreateNew}
          >
            <Plus className="w-3.5 h-3.5 text-text-tertiary shrink-0" />
            <span className="text-sm text-text-muted">Create New Session...</span>
          </div>
        </div>
      </div>
    </div>
  )
}
