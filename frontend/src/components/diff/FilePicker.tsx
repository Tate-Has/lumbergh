import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import type { DiffFile } from './types'
import { filterFiles } from './fileFilter'
import { getFileStats } from './utils'

/** The breadcrumb's file path, opened up into a filterable list of every file
 * in this diff. The prev/next arrows and ←/→ keys still work — this is for
 * jumping straight to a file you can name, in a diff too long to arrow through.
 */
export default function FilePicker({
  files,
  current,
  onSelect,
}: {
  files: DiffFile[]
  current: string
  onSelect: (path: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const statsByPath = useMemo(
    () => new Map(files.map((f) => [f.path, getFileStats(f.diff)])),
    [files]
  )
  const matches = useMemo(
    () =>
      filterFiles(
        files.map((f) => f.path),
        query
      ),
    [files, query]
  )

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onClickOutside = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  const choose = (path: string) => {
    onSelect(path)
    setOpen(false)
    setQuery('')
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setOpen(false)
      return
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      e.stopPropagation()
      setHighlight((h) => {
        const next = e.key === 'ArrowDown' ? h + 1 : h - 1
        return Math.max(0, Math.min(matches.length - 1, next))
      })
      return
    }
    if (e.key === 'Enter' && matches[highlight]) {
      e.preventDefault()
      choose(matches[highlight])
    }
  }

  return (
    <div ref={containerRef} className="relative min-w-0 flex-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 min-w-0 w-full text-left hover:bg-control-bg-hover rounded px-1 py-0.5"
        title="Jump to another file in this diff"
        data-testid="file-picker-toggle"
      >
        <span className="font-mono text-sm text-action truncate">{current}</span>
        <ChevronDown size={14} className="text-text-muted shrink-0" />
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-50 w-[min(32rem,90vw)] bg-bg-surface border border-border-default rounded-[var(--radius-xl)] shadow-xl">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border-default">
            <Search size={14} className="text-text-muted shrink-0" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setHighlight(0)
              }}
              onKeyDown={onKeyDown}
              placeholder={`Filter ${files.length} files...`}
              className="flex-1 bg-transparent text-sm outline-none text-text-primary placeholder:text-text-muted"
            />
          </div>
          <div className="max-h-80 overflow-auto py-1">
            {matches.length === 0 && (
              <div className="px-3 py-2 text-sm text-text-muted">No file matches “{query}”</div>
            )}
            {matches.map((path, i) => {
              const stats = statsByPath.get(path)
              return (
                <button
                  key={path}
                  onClick={() => choose(path)}
                  onMouseEnter={() => setHighlight(i)}
                  data-testid="file-picker-option"
                  className={`w-full flex items-center gap-3 px-3 py-1.5 text-left ${
                    i === highlight ? 'bg-control-bg-hover' : ''
                  } ${path === current ? 'text-action' : 'text-text-secondary'}`}
                >
                  <span className="font-mono text-xs truncate flex-1">{path}</span>
                  {stats && (
                    <>
                      <span className="text-success text-xs shrink-0">+{stats.additions}</span>
                      <span className="text-danger text-xs shrink-0">-{stats.deletions}</span>
                    </>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
