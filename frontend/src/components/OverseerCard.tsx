import { useState } from 'react'
import { ChevronRight, Hand } from 'lucide-react'
import SessionCard, { type Session } from './SessionCard'
import WorkerRow from './WorkerRow'
import { sessionNeedsAttention } from '../utils/sessionStatus'

interface SessionUpdate {
  displayName?: string
  description?: string
  paused?: boolean
  agentProvider?: string
  tabVisibility?: Record<string, boolean>
  cloudEnabled?: boolean
  theOne?: boolean
}

/** A parent session that owns worker sub-sessions: the full parent card, plus a
 * collapsed-by-default expander revealing compact worker rows. The worker count
 * and an attention rollup stay visible while collapsed so a stuck worker is never
 * hidden. */
export default function OverseerCard({
  parent,
  workers,
  onDelete,
  onUpdate,
  onReset,
  cloudAtLimit,
  babysat,
  onToggleBabysit,
}: {
  parent: Session
  workers: Session[]
  onDelete: (name: string, cleanupWorktree?: boolean) => void
  onUpdate: (name: string, updates: SessionUpdate) => void
  onReset: (name: string) => void
  cloudAtLimit?: boolean
  babysat?: boolean
  onToggleBabysit?: (name: string, babysat: boolean) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const attention = workers.filter(sessionNeedsAttention).length

  return (
    <div data-testid={`overseer-${parent.name}`}>
      <SessionCard
        session={parent}
        onDelete={onDelete}
        onUpdate={onUpdate}
        onReset={onReset}
        cloudAtLimit={cloudAtLimit}
        babysat={babysat}
        onToggleBabysit={onToggleBabysit}
      />
      <div className="mt-1 ml-3 border-l-2 border-border-default/60 pl-1">
        <button
          onClick={() => setExpanded((v) => !v)}
          data-testid={`overseer-toggle-${parent.name}`}
          aria-expanded={expanded}
          className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
        >
          <ChevronRight
            size={14}
            className={`flex-shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
          />
          <span className="font-medium">
            {workers.length} worker{workers.length !== 1 ? 's' : ''}
          </span>
          {attention > 0 && (
            <span className="ml-auto flex items-center gap-1 text-warning">
              <Hand size={12} />
              {attention} need{attention === 1 ? 's' : ''} you
            </span>
          )}
        </button>
        {expanded && (
          <div className="space-y-0.5 pb-1">
            {workers.map((w) => (
              <WorkerRow key={w.name} worker={w} onDelete={onDelete} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
