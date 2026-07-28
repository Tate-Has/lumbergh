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
  /**
   * Populated only for repos where EVERY linked session's stored path failed to
   * resolve (e.g. the repo folder was moved/renamed after those sessions were
   * created) — the message is the backend's actual error for the last candidate
   * tried, so it names the stale path instead of just saying "not found".
   */
  repoPathErrors: Record<string, string>
  refetch: () => void
}

/**
 * All distinct repo paths any task in this repo has ever pointed a linked
 * session at. Deliberately not just the first match — if the repo's folder
 * moved, whichever session happens to be found first may still carry the
 * stale pre-move path while a later-linked session has the current one.
 *
 * If the repo was matched against a configured search directory (repo.path
 * set by deriveRepos), that's the authoritative path — no need to go hunting
 * through linked sessions at all, and it works even for a repo with no
 * sessions linked yet.
 */
function resolveRepoPaths(repo: Repo, tasks: Task[], sessions: RawSession[]): string[] {
  if (repo.path) return [repo.path]

  const paths = new Set<string>()
  for (const task of tasks) {
    if (task.project !== repo.id || !task.session_name) continue
    const session = sessions.find((s) => s.name === task.session_name)
    const path = session?.worktreeParentRepo || session?.workdir || null
    if (path) paths.add(path)
  }
  return [...paths]
}

/**
 * Resolves candidate repo_paths per repo (via any linked session's
 * workdir/worktreeParentRepo), dedupes identical repo_paths across repos, and
 * fetches worktree lists for each. A repo's `worktreesByRepo` entry comes from
 * the first candidate path that actually resolved on the backend — so a repo
 * with one stale-pathed session and one fresh one still works. Re-fetches
 * automatically when the set of resolved repo_paths changes, and exposes a
 * manual `refetch` for callers to invoke after worktree-affecting actions.
 */
export function useWorktrees(
  repos: Repo[],
  tasks: Task[],
  sessions: RawSession[]
): UseWorktreesResult {
  const [worktreesByRepoPath, setWorktreesByRepoPath] = useState<Record<string, Worktree[]>>({})
  const [worktreePathErrors, setWorktreePathErrors] = useState<Record<string, string>>({})

  const repoPathsById = useMemo(() => {
    const map: Record<string, string[]> = {}
    for (const repo of repos) {
      map[repo.id] = resolveRepoPaths(repo, tasks, sessions)
    }
    return map
  }, [repos, tasks, sessions])

  const uniqueRepoPaths = useMemo(() => {
    const paths = new Set<string>()
    for (const list of Object.values(repoPathsById)) {
      for (const path of list) paths.add(path)
    }
    return [...paths].sort()
  }, [repoPathsById])

  const uniqueRepoPathsKey = uniqueRepoPaths.join('\n')

  const fetchWorktrees = useCallback(async () => {
    const paths = uniqueRepoPathsKey ? uniqueRepoPathsKey.split('\n') : []
    if (paths.length === 0) {
      setWorktreesByRepoPath({})
      setWorktreePathErrors({})
      return
    }

    const entries = await Promise.all(
      paths.map(async (path): Promise<[string, Worktree[] | null, string | null]> => {
        try {
          const res = await fetch(
            `${getApiBase()}/sessions/worktrees?repo_path=${encodeURIComponent(path)}`
          )
          if (!res.ok) {
            const data = await res.json().catch(() => ({}))
            return [
              path,
              null,
              data.detail || `Failed to load worktrees for ${path} (HTTP ${res.status})`,
            ]
          }
          const data = await res.json()
          return [path, data.worktrees || [], null]
        } catch (err) {
          return [
            path,
            null,
            err instanceof Error ? err.message : `Failed to reach backend for ${path}`,
          ]
        }
      })
    )

    setWorktreesByRepoPath(
      Object.fromEntries(
        entries
          .filter(([, worktrees]) => worktrees !== null)
          .map(([path, worktrees]) => [path, worktrees])
      ) as Record<string, Worktree[]>
    )
    setWorktreePathErrors(
      Object.fromEntries(
        entries.filter(([, , err]) => err !== null).map(([path, , err]) => [path, err])
      ) as Record<string, string>
    )
  }, [uniqueRepoPathsKey])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs fetched worktree data whenever the resolved repo_path set changes
    fetchWorktrees()
  }, [uniqueRepoPathsKey, fetchWorktrees])

  const worktreesByRepo = useMemo(() => {
    const result: Record<string, Worktree[]> = {}
    for (const repo of repos) {
      const candidates = repoPathsById[repo.id] || []
      const workingPath = candidates.find((path) =>
        Object.prototype.hasOwnProperty.call(worktreesByRepoPath, path)
      )
      result[repo.id] = (workingPath && worktreesByRepoPath[workingPath]) || []
    }
    return result
  }, [repos, repoPathsById, worktreesByRepoPath])

  const repoPathErrors = useMemo(() => {
    const result: Record<string, string> = {}
    for (const repo of repos) {
      const candidates = repoPathsById[repo.id] || []
      if (candidates.length === 0) continue
      const anyWorking = candidates.some((path) =>
        Object.prototype.hasOwnProperty.call(worktreesByRepoPath, path)
      )
      if (anyWorking) continue
      const message = candidates.map((path) => worktreePathErrors[path]).find(Boolean)
      result[repo.id] = message || `Repository path does not exist: ${candidates[0]}`
    }
    return result
  }, [repos, repoPathsById, worktreesByRepoPath, worktreePathErrors])

  return { worktreesByRepo, repoPathErrors, refetch: fetchWorktrees }
}
