import { Baby } from 'lucide-react'
import { canBabysit } from '../utils/babysit'

/** The per-card babysit switch: tell Bill to keep this session moving.
 *
 * Gray when off, accent when on. Renders nothing for a session that can't be babysat
 * (a worker, Bill, a scratch, or a dead-and-not-babysat session), so callers can drop it
 * into any card footer without gating it themselves. */
export default function BabysitToggle({
  session,
  babysat,
  onToggle,
}: {
  session: { name: string; role?: string | null; type?: string | null; alive: boolean }
  babysat?: boolean
  onToggle?: (name: string, babysat: boolean) => void
}) {
  const on = !!babysat
  if (!onToggle || !canBabysit(session, on)) return null

  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onToggle(session.name, on)
      }}
      data-testid="babysit-toggle"
      aria-pressed={on}
      className={`p-0.5 rounded-[var(--radius-md)] transition-colors ${
        on ? 'text-action hover:text-action/80' : 'text-text-muted hover:text-action'
      }`}
      title={
        on
          ? 'Babysitting — Bill keeps this session moving (click to stop)'
          : 'Babysit — have Bill keep this session moving'
      }
    >
      <Baby size={14} />
    </button>
  )
}
