import { useEffect, useState } from 'react'
import { Search, X } from 'lucide-react'
import { getApiBase } from '../../config'
import { hashKey, type SearchQuery } from './graphSearch'

export interface HistoryCommit {
  hash: string
  shortHash: string
  message: string
  author: string
  authorEmail?: string
  relativeDate: string
}

/** Results from searching all of history, for the queries the loaded graph
 * window cannot answer: a commit older than the limit, one on a branch the
 * graph is not showing, or a `file:` query, since the payload carries no file
 * lists at all.
 *
 * Selecting a result loads its diff the same way clicking a graph row does. A
 * commit outside the loaded window will not be highlighted in the graph — the
 * result row is the only place it appears.
 */
export function HistorySearchOverlay(props: {
  open: boolean
  sessionName?: string
  query: SearchQuery
  onClose: () => void
  onSelectCommit: (hash: string) => void
  loadedHashes: Set<string>
}) {
  const { open, sessionName, ...rest } = props
  if (!open || !sessionName) return null
  return <HistorySearchPanel sessionName={sessionName} {...rest} />
}

function describe(query: SearchQuery): string {
  const parts: string[] = []
  if (query.text) parts.push(`"${query.text}"`)
  if (query.author) parts.push(`by ${query.author}`)
  if (query.file) parts.push(`touching ${query.file}`)
  return parts.join(' ')
}

export default function HistorySearchPanel({
  sessionName,
  query,
  onClose,
  onSelectCommit,
  loadedHashes,
}: {
  sessionName: string
  query: SearchQuery
  onClose: () => void
  onSelectCommit: (hash: string) => void
  loadedHashes: Set<string>
}) {
  const [commits, setCommits] = useState<HistoryCommit[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    setCommits(null)
    setError(false)
    ;(async () => {
      const params = new URLSearchParams({ limit: '100' })
      if (query.text) params.set('q', query.text)
      if (query.author) params.set('author', query.author)
      if (query.file) params.set('file', query.file)
      try {
        const res = await fetch(
          `${getApiBase()}/sessions/${sessionName}/git/search?${params.toString()}`
        )
        if (!res.ok) throw new Error(String(res.status))
        const data = await res.json()
        if (!cancelled) setCommits(data.commits ?? [])
      } catch {
        if (!cancelled) setError(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [sessionName, query.text, query.author, query.file])

  return (
    <div
      className="absolute inset-x-2 top-2 bottom-2 z-50 flex flex-col bg-bg-surface border border-border-default rounded-[var(--radius-xl)] shadow-xl"
      data-testid="history-search-panel"
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border-default">
        <Search size={14} className="text-text-muted" />
        <span className="text-sm font-medium text-text-primary">All history</span>
        <span className="text-xs text-text-muted truncate">{describe(query)}</span>
        <button
          onClick={onClose}
          className="ml-auto text-text-tertiary hover:text-text-primary"
          title="Close"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {error && <div className="p-3 text-sm text-danger">Could not search history.</div>}
        {!error && commits === null && (
          <div className="p-3 text-sm text-text-muted">Searching all history...</div>
        )}
        {commits?.length === 0 && (
          <div className="p-3 text-sm text-text-muted">
            Nothing in history matches {describe(query)}.
          </div>
        )}
        {commits?.map((commit) => (
          <div
            key={commit.hash}
            data-testid="history-search-result"
            onClick={() => onSelectCommit(commit.hash)}
            className="flex items-center gap-3 px-3 py-1.5 border-b border-border-default/50 hover:bg-control-bg-hover cursor-pointer"
          >
            <span className="font-mono text-xs text-action w-16 shrink-0">{commit.shortHash}</span>
            <span className="text-xs text-text-secondary truncate flex-1">{commit.message}</span>
            {!loadedHashes.has(hashKey(commit.hash)) && (
              <span
                className="text-[10px] text-text-muted shrink-0 px-1.5 py-0.5 rounded bg-control-bg"
                title="Older than the commits the graph has loaded, so it is not shown above"
              >
                off-graph
              </span>
            )}
            <span className="text-xs text-text-muted w-28 shrink-0 truncate">{commit.author}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
