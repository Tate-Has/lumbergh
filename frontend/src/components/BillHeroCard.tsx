import { useNavigate } from 'react-router-dom'
import { Power, UserRoundCog } from 'lucide-react'
import GlassPanel from './ui/GlassPanel'
import type { Session } from './SessionCard'
import { getSessionStatus, statusColorClasses } from '../utils/sessionStatus'
import { getApiBase } from '../config'
import { buildBillStopMessage } from '../utils/billStop'

/** Retire Bill: warn (naming any overseers he's babysitting, since those loops keep
 * running unmonitored) then hand off to the shared session-delete path. Mirrors
 * SessionCard's confirmDeleteSession — its own fetch + confirm, so the card stays dumb. */
async function confirmStopBill(name: string, onStop: (name: string) => void) {
  let babysat: string[] = []
  try {
    const res = await fetch(`${getApiBase()}/bill/babysit`)
    if (res.ok) {
      const data = await res.json()
      babysat = (data.babysits ?? []).map((b: { session: string }) => b.session)
    }
  } catch {
    // Can't reach the registry — proceed; the warning is a courtesy, not a gate.
  }
  if (confirm(buildBillStopMessage(babysat))) {
    onStop(name)
  }
}

/** Bill, the fleet manager, promoted above the session grid. Distinct from a peer
 * card: full-width, elevated, manager icon, and a one-line supervision rollup. */
export default function BillHeroCard({
  bill,
  watching,
  needAttention,
  onStop,
}: {
  bill: Session
  watching: number
  needAttention: number
  onStop: (name: string) => void
}) {
  const navigate = useNavigate()
  const status = getSessionStatus(bill)
  const colors = statusColorClasses[status.color]

  const rollup =
    watching === 0
      ? 'no active sessions'
      : `watching ${watching} session${watching !== 1 ? 's' : ''}` +
        (needAttention > 0 ? ` · ${needAttention} need${needAttention === 1 ? 's' : ''} you` : '')

  return (
    <section className="mb-8">
      <GlassPanel
        variant="elevated"
        hover
        padding="md"
        onClick={() => navigate(`/session/${bill.name}`)}
        data-testid="bill-hero"
        className="cursor-pointer border-l-4 border-l-action flex items-center gap-4"
      >
        <div className="flex-shrink-0 w-11 h-11 rounded-full bg-action/15 text-action flex items-center justify-center">
          <UserRoundCog size={24} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-text-primary">{bill.displayName || 'Bill'}</h2>
            <span className="text-xs text-text-muted">your manager</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${colors.dot} ${status.pulse ? 'animate-pulse' : ''}`}
            />
            <span className={`text-xs ${colors.text}`}>{status.label}</span>
            <span className="text-xs text-text-muted">· {rollup}</span>
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            void confirmStopBill(bill.name, onStop)
          }}
          data-testid="stop-bill-btn"
          className="flex-shrink-0 text-text-muted hover:text-danger transition-colors p-1"
          title="Stop Bill (retire his session)"
          aria-label="Stop Bill"
        >
          <Power size={18} />
        </button>
      </GlassPanel>
    </section>
  )
}
