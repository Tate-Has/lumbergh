import { useCallback, useEffect, useRef, useState } from 'react'
import { GitBranch } from 'lucide-react'
import { useApiClient } from '../hooks/useApiClient'

interface WorktreeRow {
  path: string
  repo: string
  branch: string
  session: string | null
  agent: string | null
  state: 'active' | 'orphan'
}

interface ReapResponse {
  status?: string
  path?: string
  error?: string
  reason?: string
}

export default function WorktreePanel() {
  const api = useApiClient({})
  const [worktrees, setWorktrees] = useState<WorktreeRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reapingPath, setReapingPath] = useState<string | null>(null)
  const [refusal, setRefusal] = useState<{ path: string; message: string } | null>(null)

  // useApiClient({}) returns a new wrapper object every render (only its
  // individual methods are memoized), so we depend on the stable `api.get`
  // reference here rather than `api` itself to avoid retriggering the effect
  // below on every render.
  const apiGet = api.get
  const mountedRef = useRef(true)

  const fetchWorktrees = useCallback(async () => {
    try {
      const data = await apiGet<{ worktrees: WorktreeRow[] }>('/worktrees')
      if (mountedRef.current) {
        setWorktrees(data.worktrees || [])
        setError(null)
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to fetch worktrees')
      }
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [apiGet])

  useEffect(() => {
    mountedRef.current = true
    fetchWorktrees()
    return () => {
      mountedRef.current = false
    }
  }, [fetchWorktrees])

  const reap = async (path: string) => {
    setReapingPath(path)
    setRefusal(null)
    try {
      const res = await api.post<ReapResponse>('/worktrees/reap', { path })
      if (res.error) {
        setRefusal({
          path,
          message: res.reason ? `${res.error} (${res.reason})` : res.error,
        })
      } else {
        await fetchWorktrees()
      }
    } catch (err) {
      setRefusal({
        path,
        message: err instanceof Error ? err.message : 'Failed to reap worktree',
      })
    } finally {
      setReapingPath(null)
    }
  }

  if (loading) return null
  if (!worktrees.length && !error) return null

  return (
    <section className="mb-8" data-testid="worktree-panel">
      <h2 className="text-sm font-medium text-text-tertiary mb-3 uppercase tracking-wide">
        Worktrees
      </h2>

      {error && <div className="mb-2 p-2 bg-danger/15 text-danger text-sm rounded">{error}</div>}

      {worktrees.length > 0 && (
        <div className="space-y-1">
          {worktrees.map((w) => (
            <div
              key={w.path}
              className="flex items-center justify-between gap-2 p-2 bg-bg-surface rounded text-sm"
              data-testid={`worktree-row-${w.path}`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <GitBranch size={14} className="text-text-tertiary flex-shrink-0" />
                <span className="truncate text-text-secondary" title={w.path}>
                  {w.branch}
                </span>
                {w.state === 'orphan' && (
                  <span
                    data-testid="orphan-badge"
                    className="flex-shrink-0 rounded bg-warning/20 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-warning"
                  >
                    Orphan
                  </span>
                )}
                {w.session && (
                  <span className="truncate text-xs text-text-muted">→ {w.session}</span>
                )}
              </div>
              <button
                onClick={() => reap(w.path)}
                disabled={reapingPath === w.path}
                className="flex-shrink-0 text-xs px-2 py-1 text-danger hover:bg-danger/10 rounded disabled:opacity-50 transition-colors"
              >
                {reapingPath === w.path ? 'Reaping...' : 'Reap'}
              </button>
            </div>
          ))}
        </div>
      )}

      {refusal && (
        <div
          role="alert"
          data-testid="reap-refusal"
          className="mt-2 p-2 bg-warning/15 text-warning text-sm rounded"
        >
          Reap blocked for <span className="font-mono">{refusal.path}</span>: {refusal.message}
        </div>
      )}
    </section>
  )
}
