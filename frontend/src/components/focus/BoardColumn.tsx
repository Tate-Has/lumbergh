import { useRef, useState, useCallback } from 'react'
import KanbanCard from './KanbanCard'
import { KANBAN_LABELS } from '../../types/focusConstants'
import type { Task } from '../../types/focus'

interface BoardColumnProps {
  status: string
  label: string
  tasks: Task[]
  isCollapsed: boolean
  onToggleCollapse?: () => void
  wipLimit?: number
  isDone: boolean
  isWaiting: boolean
  isBacklog: boolean
  onEditTask: (task: Task) => void
  onAddTask: () => void
  onPromoteToday: (taskId: string) => void
  onArchiveDone?: () => void
  onDropTask: (taskId: string, status: string, beforeTaskId: string | null) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
}

export default function BoardColumn({
  status,
  tasks,
  isCollapsed,
  onToggleCollapse,
  wipLimit,
  isDone,
  isWaiting,
  isBacklog,
  onEditTask,
  onAddTask,
  onPromoteToday,
  onArchiveDone,
  onDropTask,
  getDragHandlers,
}: BoardColumnProps) {
  const cardsRef = useRef<HTMLDivElement>(null)
  const [activeBeforeTaskId, setActiveBeforeTaskId] = useState<string | null>(null)

  const isOverWip = wipLimit != null && tasks.length > wipLimit

  // -----------------------------------------------------------------------
  // All hooks must be declared before any conditional return to satisfy
  // React's Rules of Hooks (same number/order every render).
  // -----------------------------------------------------------------------

  const handleCollapsedDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const handleCollapsedDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const taskId = e.dataTransfer.getData('text/plain')
      if (taskId) {
        onDropTask(taskId, status, null)
      }
    },
    [onDropTask, status]
  )

  const findBeforeTaskId = useCallback((clientY: number): string | null => {
    const container = cardsRef.current
    if (!container) return null

    const cards = container.querySelectorAll<HTMLElement>('.kanban-card')
    let closest: { id: string | null; offset: number } = {
      id: null,
      offset: Number.POSITIVE_INFINITY,
    }

    for (const card of cards) {
      const box = card.getBoundingClientRect()
      const midY = box.top + box.height / 2
      const offset = clientY - midY

      // We want the card that the cursor is just above (offset < 0 and smallest magnitude)
      if (offset < 0 && Math.abs(offset) < closest.offset) {
        closest = { id: card.dataset.taskId || null, offset: Math.abs(offset) }
      }
    }

    return closest.id
  }, [])

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
      const beforeId = findBeforeTaskId(e.clientY)
      setActiveBeforeTaskId(beforeId)
    },
    [findBeforeTaskId]
  )

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    const container = cardsRef.current
    if (container && !container.contains(e.relatedTarget as Node)) {
      setActiveBeforeTaskId(null)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      const taskId = e.dataTransfer.getData('text/plain')
      if (taskId) {
        onDropTask(taskId, status, findBeforeTaskId(e.clientY))
      }
      setActiveBeforeTaskId(null)
    },
    [onDropTask, status, findBeforeTaskId]
  )

  const handleCollapseClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onToggleCollapse?.()
    },
    [onToggleCollapse]
  )

  const handleArchiveClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onArchiveDone?.()
    },
    [onArchiveDone]
  )

  // -----------------------------------------------------------------------
  // Collapsed column rendering (after all hooks)
  // -----------------------------------------------------------------------

  if (isCollapsed) {
    return (
      <div
        className="board-col collapsed-col flex-1 min-w-[40px] max-w-[40px] bg-bg-surface rounded-[10px] px-1.5 py-2.5 cursor-pointer items-center transition-all duration-200 ease-in-out flex flex-col hover:bg-bg-elevated"
        data-status={status}
        onClick={onToggleCollapse}
        onDragOver={handleCollapsedDragOver}
        onDrop={handleCollapsedDrop}
      >
        <span className="collapsed-col-label [writing-mode:vertical-rl] [text-orientation:mixed] text-xs font-semibold text-text-muted uppercase tracking-[0.04em] whitespace-nowrap">
          {KANBAN_LABELS[status]}
        </span>
        <span className="collapsed-col-count text-[0.7rem] font-semibold text-text-muted bg-bg-elevated rounded-lg px-1.5 py-0.5 mt-2">
          {tasks.length}
        </span>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div
      className={`board-col flex-1 min-w-[200px] max-w-[300px] bg-bg-surface rounded-xl p-3 flex flex-col${isWaiting ? ' waiting-col bg-waiting-col-bg' : ''}${isDone ? ' done-col' : ''}`}
      data-status={status}
    >
      <div
        className={`col-header flex items-center justify-between mb-2.5${isOverWip ? ' wip-warning border-b-2 border-b-priority-high' : ''}`}
      >
        <span className="col-title text-xs font-semibold text-text-muted uppercase tracking-[0.04em]">
          {KANBAN_LABELS[status]}
        </span>
        <div className="flex items-center gap-1.5">
          <span
            className={`col-count text-[0.7rem] font-semibold text-text-muted bg-bg-elevated rounded-lg px-[7px] py-px${isOverWip ? ' wip-over !bg-priority-high-bg !text-priority-high' : ''}`}
          >
            {tasks.length}
            {wipLimit != null ? `/${wipLimit}` : ''}
          </span>
          {isBacklog && (
            <button
              className="topbar-btn !px-1.5 !py-0.5 !text-[0.7rem]"
              onClick={handleCollapseClick}
            >
              &#x25C0;
            </button>
          )}
          {isDone && (
            <>
              <button
                className="topbar-btn !px-1.5 !py-0.5 !text-[0.7rem]"
                id="collapseDone"
                onClick={handleCollapseClick}
              >
                &#x25B6;
              </button>
              {tasks.length > 0 && onArchiveDone && (
                <button
                  className="archive-done-btn bg-transparent border border-border-default text-[0.65rem] font-semibold text-text-muted cursor-pointer px-2 py-0.5 rounded transition-all duration-150 ease-in-out hover:text-accent hover:bg-orange-subtle hover:border-accent"
                  id="archiveDoneBtn"
                  title="Archive all done tasks"
                  onClick={handleArchiveClick}
                >
                  Archive ({tasks.length})
                </button>
              )}
            </>
          )}
        </div>
      </div>

      <div
        className="col-cards flex flex-col gap-2 flex-1 min-h-[40px]"
        data-status={status}
        ref={cardsRef}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {tasks.map((task) => (
          <div key={task.id}>
            <div
              className={`insert-line${activeBeforeTaskId === task.id ? ' visible' : ''}`}
              data-before-task={task.id}
            />
            <KanbanCard
              task={task}
              isWaiting={isWaiting}
              isDone={isDone}
              dragHandlers={getDragHandlers(task.id)}
              onEdit={() => onEditTask(task)}
              onPromoteToday={() => onPromoteToday(task.id)}
            />
          </div>
        ))}
        {/* Trailing insert line (drop at end) */}
        <div
          className={`insert-line${activeBeforeTaskId === null && tasks.length > 0 ? ' visible' : ''}`}
          data-before-task="__end__"
        />
      </div>

      {!isDone && (
        <button
          className="col-add-btn bg-transparent border border-dashed border-border-default rounded-md py-2 px-3 text-xs text-text-muted cursor-pointer transition-all duration-150 ease-in-out mt-2 text-center hover:border-accent hover:text-accent hover:bg-orange-subtle"
          data-status={status}
          onClick={onAddTask}
        >
          + Add
        </button>
      )}
    </div>
  )
}
