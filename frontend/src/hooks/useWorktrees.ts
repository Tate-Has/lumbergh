import { useCallback, useEffect, useState } from 'react'
import { getApiBase } from '../config'

export interface Worktree {
  path: string
  repo: string
  parent_repo: string
  branch: string | null
  session: string | null
  agent: string | null
  task_intent: string | null
  state: 'active' | 'orphan'
}

/** Every worktree sharing this session's repo, and a way to reload after a reap.
 *
 * Keyed on the session name rather than a path: the Git tab never learns one, and
 * the server resolves the parent repo (a session that is itself a worktree wants
 * its siblings, not itself). */
export function useWorktrees(sessionName: string | undefined) {
  const [worktrees, setWorktrees] = useState<Worktree[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!sessionName) return
    setLoading(true)
    try {
      const res = await fetch(`${getApiBase()}/worktrees/for-session/${sessionName}`)
      if (!res.ok) return
      const data = await res.json()
      setWorktrees(Array.isArray(data.worktrees) ? data.worktrees : [])
    } catch {
      // Leave the last known list up: a failed refresh is not evidence that the
      // worktrees went away, and blanking the panel would imply it.
    } finally {
      setLoading(false)
    }
  }, [sessionName])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { worktrees, loading, refresh }
}

/** Which branches are held by a worktree, for marking them in a branch list. */
export function claimedBranches(worktrees: Worktree[]): Map<string, Worktree> {
  const byBranch = new Map<string, Worktree>()
  for (const wt of worktrees) {
    if (wt.branch) byBranch.set(wt.branch, wt)
  }
  return byBranch
}
