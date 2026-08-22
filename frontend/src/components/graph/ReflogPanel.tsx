import { useEffect, useState } from 'react'
import { History, X } from 'lucide-react'
import { getApiBase } from '../../config'

export interface ReflogEntry {
  hash: string
  shortHash: string
  selector: string
  action: string
  message: string
  relativeDate: string
}

/** Colour by what moved HEAD: the destructive ones are the reason you are here. */
const ACTION_TONE: Record<string, string> = {
  reset: 'text-danger',
  rebase: 'text-warning',
  merge: 'text-warning',
  checkout: 'text-text-muted',
  commit: 'text-success',
}

/** "Where was I?" — recent HEAD movements, including the ones the graph can no
 * longer show.
 *
 * After a bad reset or an abandoned rebase the commit you want is unreachable,
 * so the graph and `git log` are exactly the wrong places to look: they only
 * walk history that survived. Recovering means branching from the entry (safe,
 * keeps everything) or resetting back onto it.
 */
/** Mounts the panel only when it is open and there is a session to read from,
 * so the graph itself carries no branching for it. */
export function ReflogOverlay(props: {
  open: boolean
  sessionName?: string
  onClose: () => void
  onBranchFrom: (entry: ReflogEntry) => void
  onResetTo: (entry: ReflogEntry) => void
}) {
  const { open, sessionName, ...rest } = props
  if (!open || !sessionName) return null
  return <ReflogPanel sessionName={sessionName} {...rest} />
}

export default function ReflogPanel({
  sessionName,
  onClose,
  onBranchFrom,
  onResetTo,
}: {
  sessionName: string
  onClose: () => void
  onBranchFrom: (entry: ReflogEntry) => void
  onResetTo: (entry: ReflogEntry) => void
}) {
  const [entries, setEntries] = useState<ReflogEntry[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${getApiBase()}/sessions/${sessionName}/git/reflog?limit=50`)
        if (!res.ok) throw new Error(String(res.status))
        const data = await res.json()
        if (!cancelled) setEntries(data.entries ?? [])
      } catch {
        if (!cancelled) setError(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [sessionName])

  return (
    <div
      className="absolute inset-x-2 top-2 bottom-2 z-50 flex flex-col bg-bg-surface border border-border-default rounded-[var(--radius-xl)] shadow-xl"
      data-testid="reflog-panel"
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border-default">
        <History size={14} className="text-text-muted" />
        <span className="text-sm font-medium text-text-primary">Where was I?</span>
        <span className="text-xs text-text-muted">
          every commit HEAD has pointed at, including ones the graph dropped
        </span>
        <button
          onClick={onClose}
          className="ml-auto text-text-tertiary hover:text-text-primary"
          title="Close"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {error && <div className="p-3 text-sm text-danger">Could not read the reflog.</div>}
        {!error && entries === null && (
          <div className="p-3 text-sm text-text-muted">Reading history...</div>
        )}
        {entries?.length === 0 && (
          <div className="p-3 text-sm text-text-muted">Nothing in the reflog yet.</div>
        )}
        {entries?.map((entry) => (
          <div
            key={entry.selector}
            data-testid="reflog-entry"
            className="group flex items-center gap-3 px-3 py-1.5 border-b border-border-default/50 hover:bg-control-bg-hover"
          >
            <span className="font-mono text-xs text-text-muted w-20 shrink-0">
              {entry.selector}
            </span>
            <span className="font-mono text-xs text-action w-16 shrink-0">{entry.shortHash}</span>
            <span
              className={`text-xs w-16 shrink-0 truncate ${ACTION_TONE[entry.action] ?? 'text-text-muted'}`}
            >
              {entry.action}
            </span>
            <span className="text-xs text-text-secondary truncate flex-1">{entry.message}</span>
            <span className="text-xs text-text-muted shrink-0">{entry.relativeDate}</span>
            <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => onBranchFrom(entry)}
                className="px-2 py-0.5 text-xs rounded bg-control-bg hover:bg-control-bg-hover text-text-secondary"
                title="Create a branch here — recovers the commit without moving anything"
              >
                Branch here
              </button>
              <button
                onClick={() => onResetTo(entry)}
                className="px-2 py-0.5 text-xs rounded bg-control-bg hover:bg-danger/10 text-danger"
                title="Reset this branch back to here (hard)"
              >
                Reset here
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
