import { useState, useEffect, useCallback, useMemo } from 'react'
import { getApiBase } from '../config'
import type { Task } from '../types/focus'
import type { SessionBase } from '../utils/sessionStatus'
import type { Repo } from '../utils/repos'

export interface RawSession extends SessionBase {
  workdir?: string | null
  worktreeParentRepo?: string | null
  worktreeBranch?: string | null
}

export interface Worktree {
  path: string
  branch: string
  commit: string
  is_main: boolean
  last_activity: string | null
  stale: boolean
}

export interface UseWorktreesResult {
  worktreesByRepo: Record<string, Worktree[]>
  refetch: () => void
}

function resolveRepoPath(repo: Repo, tasks: Task[], sessions: RawSession[]): string | null {
  const task = tasks.find((t) => t.project === repo.id && !!t.session_name)
  if (!task) return null

  const session = sessions.find((s) => s.name === task.session_name)
  if (!session) return null

  return session.worktreeParentRepo || session.workdir || null
}

/**
 * Resolves a repo_path per repo (via any linked session's workdir/worktreeParentRepo),
 * dedupes identical repo_paths across repos, and fetches worktree lists for each.
 * Re-fetches automatically when the set of resolved repo_paths changes, and exposes
 * a manual `refetch` for callers to invoke after worktree-affecting actions.
 */
export function useWorktrees(
  repos: Repo[],
  tasks: Task[],
  sessions: RawSession[]
): UseWorktreesResult {
  const [worktreesByRepoPath, setWorktreesByRepoPath] = useState<Record<string, Worktree[]>>({})

  const repoPathById = useMemo(() => {
    const map: Record<string, string | null> = {}
    for (const repo of repos) {
      map[repo.id] = resolveRepoPath(repo, tasks, sessions)
    }
    return map
  }, [repos, tasks, sessions])

  const uniqueRepoPaths = useMemo(() => {
    const paths = new Set<string>()
    for (const path of Object.values(repoPathById)) {
      if (path) paths.add(path)
    }
    return [...paths].sort()
  }, [repoPathById])

  const uniqueRepoPathsKey = uniqueRepoPaths.join('\n')

  const fetchWorktrees = useCallback(async () => {
    const paths = uniqueRepoPathsKey ? uniqueRepoPathsKey.split('\n') : []
    if (paths.length === 0) return

    const entries = await Promise.all(
      paths.map(async (path): Promise<[string, Worktree[]]> => {
        try {
          const res = await fetch(
            `${getApiBase()}/sessions/worktrees?repo_path=${encodeURIComponent(path)}`
          )
          if (!res.ok) return [path, []]
          const data = await res.json()
          return [path, data.worktrees || []]
        } catch {
          return [path, []]
        }
      })
    )

    setWorktreesByRepoPath(Object.fromEntries(entries))
  }, [uniqueRepoPathsKey])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs fetched worktree data whenever the resolved repo_path set changes
    fetchWorktrees()
  }, [uniqueRepoPathsKey, fetchWorktrees])

  const worktreesByRepo = useMemo(() => {
    const result: Record<string, Worktree[]> = {}
    for (const repo of repos) {
      const path = repoPathById[repo.id]
      result[repo.id] = (path && worktreesByRepoPath[path]) || []
    }
    return result
  }, [repos, repoPathById, worktreesByRepoPath])

  return { worktreesByRepo, refetch: fetchWorktrees }
}
