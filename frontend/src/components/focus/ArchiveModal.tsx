import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import type { ArchiveTask, ArchiveData } from '../../hooks/useArchive'

export interface ArchiveModalProps {
  isOpen: boolean
  data: ArchiveData | null
  loading: boolean
  onClose: () => void
}

function escapeHtml(str: string): string {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

function highlightMatch(escapedHtml: string, query: string): string {
  if (!query) return escapedHtml
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return escapedHtml.replace(regex, '<mark class="archive-highlight">$1</mark>')
}

function formatArchiveDate(dateStr: string, isNotes: boolean): string {
  try {
    const d = new Date(dateStr + 'T00:00:00')
    if (isNaN(d.getTime())) return dateStr
    const formatted = d.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
    return isNotes ? `Notes -- ${formatted}` : formatted
  } catch {
    return dateStr
  }
}

interface DateSection {
  key: string
  dateStr: string
  isNotes: boolean
  tasks: ArchiveTask[]
  noteContent?: string
}

function groupByDate(data: ArchiveData): DateSection[] {
  const groups = new Map<string, DateSection>()

  for (const t of data.tasks || []) {
    const date = t.archived_date || 'unknown'
    if (!groups.has(date)) {
      groups.set(date, { key: date, dateStr: date, isNotes: false, tasks: [] })
    }
    groups.get(date)!.tasks.push(t)
  }

  for (const n of data.notes || []) {
    const key = `notes-${n.date}`
    groups.set(key, {
      key,
      dateStr: n.date,
      isNotes: true,
      tasks: [],
      noteContent: n.content,
    })
  }

  const sortedKeys = [...groups.keys()].sort((a, b) => {
    const da = a.replace('notes-', '')
    const db = b.replace('notes-', '')
    if (da !== db) return db.localeCompare(da)
    return a.includes('notes') ? 1 : -1
  })

  return sortedKeys.map((k) => groups.get(k)!)
}

export default function ArchiveModal({ isOpen, data, loading, onClose }: ArchiveModalProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set())
  const searchRef = useRef<HTMLInputElement>(null)
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Reset search when modal opens
  /* eslint-disable react-hooks/set-state-in-effect -- intentional: reset local form state when modal opens */
  useEffect(() => {
    if (isOpen) {
      setSearchQuery('')
      setDebouncedQuery('')
      setCollapsedSections(new Set())
      setTimeout(() => searchRef.current?.focus(), 100)
    }
  }, [isOpen])
  /* eslint-enable react-hooks/set-state-in-effect */

  // Debounce search input
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      setDebouncedQuery(searchQuery)
    }, 200)
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [searchQuery])

  const query = debouncedQuery.toLowerCase().trim()

  const sections = useMemo(() => {
    if (!data) return []
    return groupByDate(data)
  }, [data])

  const { filteredSections, totalTasks, matchedTasks } = useMemo(() => {
    let total = 0
    let matched = 0
    const filtered: (DateSection & { filteredTasks: ArchiveTask[] })[] = []

    for (const section of sections) {
      total += section.tasks.length
      const ft = query
        ? section.tasks.filter(
            (t) =>
              (t.title || '').toLowerCase().includes(query) ||
              (t.project || '').toLowerCase().includes(query)
          )
        : section.tasks
      matched += ft.length
      if (ft.length > 0) {
        filtered.push({ ...section, filteredTasks: ft })
      }
    }

    return { filteredSections: filtered, totalTasks: total, matchedTasks: matched }
  }, [sections, query])

  const toggleSection = useCallback((key: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }, [])

  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  const statsText = query
    ? `${matchedTasks} of ${totalTasks} tasks match`
    : `${totalTasks} archived task${totalTasks !== 1 ? 's' : ''}`

  function renderBody() {
    if (loading) {
      return (
        <div className="archive-empty text-center text-text-muted text-[0.82rem] py-10">
          Loading archive...
        </div>
      )
    }

    if (!data) {
      return (
        <div className="archive-empty text-center text-text-muted text-[0.82rem] py-10">
          Could not load archive.
        </div>
      )
    }

    if (sections.length === 0) {
      return (
        <div className="archive-empty text-center text-text-muted text-[0.82rem] py-10">
          No archived items.
        </div>
      )
    }

    if (filteredSections.length === 0) {
      return (
        <div className="archive-empty text-center text-text-muted text-[0.82rem] py-10">
          No matches found.
        </div>
      )
    }

    return filteredSections.map((section) => {
      const isCollapsed = collapsedSections.has(section.key)
      const displayDate = formatArchiveDate(section.dateStr, section.isNotes)

      return (
        <div className="archive-date-section mb-4" data-date={section.key} key={section.key}>
          <div
            className="archive-date-header flex items-center gap-2 cursor-pointer py-1.5 select-none"
            data-toggle={section.key}
            onClick={() => toggleSection(section.key)}
          >
            <span
              className={`chevron text-[0.7rem] text-text-muted transition-transform duration-150 ease-[ease] ${isCollapsed ? ' collapsed -rotate-90' : ''}`}
            >
              &#x25BC;
            </span>
            <span className="archive-date-label text-[0.82rem] font-bold text-text-primary">
              {displayDate}
            </span>
            <span className="archive-date-count text-[0.7rem] text-text-muted font-medium">
              {section.filteredTasks.length} item
              {section.filteredTasks.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div
            className={`archive-task-list pl-1${isCollapsed ? ' hidden' : ''}`}
            data-list={section.key}
          >
            {section.filteredTasks.map((t, i) => {
              const titleHtml = query
                ? highlightMatch(escapeHtml(t.title), query)
                : escapeHtml(t.title)
              const projHtml = t.project
                ? query
                  ? highlightMatch(escapeHtml(t.project), query)
                  : escapeHtml(t.project)
                : ''

              return (
                <div
                  className="archive-task flex items-baseline gap-2 py-1 px-2 text-[0.78rem] text-text-secondary rounded hover:bg-bg-base"
                  key={`${section.key}-${i}`}
                >
                  {projHtml && (
                    <span
                      className="project-tag text-[0.68rem] font-semibold text-accent whitespace-nowrap"
                      dangerouslySetInnerHTML={{
                        __html: `[${projHtml}]`,
                      }}
                    />
                  )}
                  <span
                    className="task-title flex-1"
                    dangerouslySetInnerHTML={{ __html: titleHtml }}
                  />
                  {t.priority && t.priority !== 'med' && (
                    <span
                      className={`priority-tag text-[0.65rem] font-semibold py-px px-[5px] rounded-[3px] ${t.priority === 'high' ? ' bg-priority-high-bg text-priority-high' : t.priority === 'low' ? ' bg-priority-low-bg text-priority-low' : ''}`}
                    >
                      {t.priority}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )
    })
  }

  return (
    <div
      className={`archive-overlay fixed inset-0 bg-black/40 items-center justify-center z-[100] ${isOpen ? ' active flex' : ' hidden'}`}
      id="archiveOverlay"
      onClick={handleOverlayClick}
    >
      <div className="archive-modal bg-bg-elevated border border-border-default rounded-xl w-[680px] max-w-[90vw] max-h-[85vh] flex flex-col shadow-modal">
        <div className="archive-header flex items-center justify-between pt-5 px-6 pb-4 border-b border-border-default shrink-0">
          <h3 className="text-[0.95rem] font-bold text-text-primary m-0">Archive</h3>
          <div className="archive-search-wrap flex-[0_0_220px]">
            <input
              type="text"
              id="archiveSearch"
              className="archive-search w-full py-1.5 px-3 text-[0.78rem] border border-border-default rounded-md bg-bg-base text-text-primary outline-none focus:border-accent"
              placeholder="Search archive..."
              autoComplete="off"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              ref={searchRef}
            />
          </div>
        </div>
        <div className="archive-body flex-[1_1_auto] overflow-y-auto py-4 px-6" id="archiveBody">
          {renderBody()}
        </div>
        <div className="archive-footer flex items-center justify-between py-4 px-6 border-t border-border-default shrink-0">
          <span className="archive-stats text-[0.72rem] text-text-muted" id="archiveStats">
            {data && !loading ? statsText : ''}
          </span>
          <button
            className="modal-btn cancel archive-close-btn py-[7px] px-4 rounded-md text-[0.8rem] font-semibold cursor-pointer border border-border-default transition-all duration-150 ease-[ease] bg-transparent text-text-secondary hover:bg-bg-surface"
            id="archiveClose"
            type="button"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
