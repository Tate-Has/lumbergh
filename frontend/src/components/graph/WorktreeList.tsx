import { useState } from 'react'
import { getApiBase } from '../../config'
import { useToast } from '../../hooks/toastContext'
import type { Worktree } from '../../hooks/useWorktrees'
import { describeLoss } from '../../utils/reapLoss'

function shorten(path: string): string {
  const home = '/home/'
  if (!path.startsWith(home)) return path
  const rest = path.slice(home.length)
  const slash = rest.indexOf('/')
  return slash === -1 ? path : `~${rest.slice(slash)}`
}

interface Props {
  worktrees: Worktree[]
  onChanged: () => void
  /** The session whose Git tab this is, so it can be marked "you are here". */
  currentSession?: string
}

export default function WorktreeList({ worktrees, onChanged, currentSession }: Props) {
  const toast = useToast()
  const [busy, setBusy] = useState<string | null>(null)

  const remove = async (wt: Worktree, force: boolean) => {
    setBusy(wt.path)
    try {
      const res = await fetch(`${getApiBase()}/worktrees/reap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: wt.path, force }),
      })
      const data = await res.json().catch(() => ({}))

      if (data?.error) {
        const loss = describeLoss(data)
        if (!force && window.confirm(`Remove ${wt.branch ?? wt.path} anyway?\n\n${loss}`)) {
          await remove(wt, true)
          return
        }
        if (!force) toast.error(`Kept ${wt.branch ?? 'the worktree'}`, loss)
        else toast.error('Could not remove the worktree', data.error)
        return
      }
      toast.info(`Removed ${wt.branch ?? 'worktree'}`)
      onChanged()
    } catch {
      toast.error('Could not reach the server')
    } finally {
      setBusy(null)
    }
  }

  if (!worktrees.length) {
    return <p className="text-xs text-text-muted px-3 py-2">No worktrees for this repo.</p>
  }

  return (
    <ul className="divide-y divide-border-default" data-testid="worktree-list">
      {worktrees.map((wt) => {
        const here = wt.session && wt.session === currentSession
        return (
          <li key={wt.path} className="flex items-center gap-3 px-3 py-2 text-sm">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono truncate">{wt.branch ?? '(detached)'}</span>
                {here && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-inset text-text-muted shrink-0">
                    you are here
                  </span>
                )}
                {wt.state === 'orphan' && (
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded bg-bg-inset text-text-muted shrink-0"
                    title="No live session is attached to this worktree"
                  >
                    no session
                  </span>
                )}
              </div>
              <p className="text-xs text-text-muted truncate font-mono">{shorten(wt.path)}</p>
              {wt.task_intent && (
                <p className="text-xs text-text-muted truncate">{wt.task_intent}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => remove(wt, false)}
              disabled={busy === wt.path || Boolean(here)}
              title={here ? 'This is the worktree you are working in' : 'Remove this worktree'}
              data-testid={`worktree-remove-${wt.branch ?? wt.path}`}
              className="shrink-0 px-2 py-1 text-xs rounded-[var(--radius-md)] border border-border-default hover:bg-bg-hover disabled:opacity-40"
            >
              {busy === wt.path ? '…' : 'Remove'}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
