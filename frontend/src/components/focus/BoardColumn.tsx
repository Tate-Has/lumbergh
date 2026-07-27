import { useRef, useState, useCallback } from 'react'
import KanbanCard from './KanbanCard'
import { KANBAN_LABELS } from '../../types/focusConstants'
import type { Task } from '../../types/focus'
import type { SessionStatusInfo } from '../../hooks/useSessionStatus'
import type { Worktree } from '../../hooks/useWorktrees'
import type { LaunchAgentChoice } from './LaunchAgentForm'

interface BacklogCompactRowProps {
  task: Task
  worktreeBranch?: string
  dragHandlers: {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  onEditTask: (task: Task) => void
}

/** Compact single-line row used for the backlog column's collapsed/compact mode. */
function BacklogCompactRow({
  task,
  worktreeBranch,
  dragHandlers,
  onEditTask,
}: BacklogCompactRowProps) {
  return (
    <div
      className="backlog-compact-row flex items-center gap-1.5 px-1.5 py-1 rounded-md cursor-pointer hover:bg-bg-elevated"
      data-task-id={task.id}
      draggable={dragHandlers.draggable}
      onDragStart={dragHandlers.onDragStart}
      onDragEnd={dragHandlers.onDragEnd}
      onClick={() => onEditTask(task)}
    >
      <span
        className={`shrink-0 w-1.5 h-1.5 rounded-full ${task.priority === 'high' ? 'bg-priority-high' : task.priority === 'med' ? 'bg-priority-med' : 'bg-priority-low'}`}
      />
      <span className="flex-1 min-w-0 truncate text-[0.72rem] text-text-primary">{task.title}</span>
      {worktreeBranch && (
        <span className="shrink-0 text-[0.6rem] font-mono text-purple truncate max-w-[4rem]">
          {worktreeBranch}
        </span>
      )}
    </div>
  )
}

interface ColumnHeaderProps {
  status: string
  taskCount: number
  isOverWip: boolean
  wipLimit?: number
  isBacklog: boolean
  isDone: boolean
  backlogCollapsed?: boolean
  onHeaderClick?: (e: React.MouseEvent) => void
  onCollapseClick: (e: React.MouseEvent) => void
  onArchiveClick: (e: React.MouseEvent) => void
  showArchiveButton: boolean
}

function ColumnHeader({
  status,
  taskCount,
  isOverWip,
  wipLimit,
  isBacklog,
  isDone,
  backlogCollapsed,
  onHeaderClick,
  onCollapseClick,
  onArchiveClick,
  showArchiveButton,
}: ColumnHeaderProps) {
  return (
    <div
      className={`col-header flex items-center justify-between mb-2.5${isOverWip ? ' wip-warning border-b-2 border-b-priority-high' : ''}${isBacklog ? ' cursor-pointer' : ''}`}
      onClick={onHeaderClick}
    >
      <div className="flex items-center gap-1.5">
        {isBacklog && (
          <span
            className={`backlog-chevron text-[0.65rem] text-text-muted transition-transform duration-200 ease-in-out${backlogCollapsed ? '' : ' rotate-90'}`}
          >
            &#x25B6;
          </span>
        )}
        <span className="col-title text-xs font-semibold text-text-muted uppercase tracking-[0.04em]">
          {KANBAN_LABELS[status]}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span
          className={`col-count text-[0.7rem] font-semibold text-text-muted bg-bg-elevated rounded-lg px-[7px] py-px${isOverWip ? ' wip-over !bg-status-error-bg !text-status-error' : ''}`}
        >
          {taskCount}
          {wipLimit != null ? `/${wipLimit}` : ''}
        </span>
        {isBacklog && (
          <button className="topbar-btn !px-1.5 !py-0.5 !text-[0.7rem]" onClick={onCollapseClick}>
            &#x25C0;
          </button>
        )}
        {isDone && (
          <>
            <button
              className="topbar-btn !px-1.5 !py-0.5 !text-[0.7rem]"
              id="collapseDone"
              onClick={onCollapseClick}
            >
              &#x25B6;
            </button>
            {showArchiveButton && (
              <button
                className="archive-done-btn bg-transparent border border-border-default text-[0.65rem] font-semibold text-text-muted cursor-pointer px-2 py-0.5 rounded transition-all duration-150 ease-in-out hover:text-accent hover:bg-orange-subtle hover:border-accent"
                id="archiveDoneBtn"
                title="Archive all done tasks"
                onClick={onArchiveClick}
              >
                Archive ({taskCount})
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

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
  backlogCollapsed?: boolean
  onToggleBacklogCollapsed?: () => void
  onEditTask: (task: Task) => void
  onAddTask: () => void
  onArchiveDone?: () => void
  onDropTask: (taskId: string, status: string, beforeTaskId: string | null) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  worktreeBranchByTaskId?: Record<string, string | undefined>
  sessionStatusByTaskId?: Record<string, SessionStatusInfo | undefined>
  worktreesForRepo?: Worktree[]
  onLaunchAgent?: (taskId: string, choice: LaunchAgentChoice) => void
  onOpenSessionPicker?: (task: Task) => void
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
  backlogCollapsed,
  onToggleBacklogCollapsed,
  onEditTask,
  onAddTask,
  onArchiveDone,
  onDropTask,
  getDragHandlers,
  worktreeBranchByTaskId,
  sessionStatusByTaskId,
  worktreesForRepo,
  onLaunchAgent,
  onOpenSessionPicker,
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

  const handleBacklogHeaderClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onToggleBacklogCollapsed?.()
    },
    [onToggleBacklogCollapsed]
  )

  // -----------------------------------------------------------------------
  // Collapsed column rendering (after all hooks)
  // -----------------------------------------------------------------------

  if (isCollapsed) {
    return (
      <div
        className="board-col collapsed-col flex-1 min-w-[40px] max-w-[40px] bg-bg-sunken border border-border-subtle rounded-[10px] px-1.5 py-2.5 cursor-pointer items-center transition-all duration-200 ease-in-out flex flex-col hover:bg-bg-elevated"
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
      className={`board-col flex-1 min-w-[200px] max-w-[300px] bg-bg-sunken border border-border-subtle rounded-xl p-3 flex flex-col${isWaiting ? ' waiting-col bg-waiting-col-bg' : ''}${isDone ? ' done-col' : ''}`}
      data-status={status}
    >
      <ColumnHeader
        status={status}
        taskCount={tasks.length}
        isOverWip={isOverWip}
        wipLimit={wipLimit}
        isBacklog={isBacklog}
        isDone={isDone}
        backlogCollapsed={backlogCollapsed}
        onHeaderClick={isBacklog ? handleBacklogHeaderClick : undefined}
        onCollapseClick={handleCollapseClick}
        onArchiveClick={handleArchiveClick}
        showArchiveButton={tasks.length > 0 && !!onArchiveDone}
      />

      {isBacklog && backlogCollapsed ? (
        <div
          className="col-cards flex flex-col gap-1 flex-1 min-h-[40px]"
          data-status={status}
          ref={cardsRef}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {tasks.map((task) => (
            <BacklogCompactRow
              key={task.id}
              task={task}
              worktreeBranch={worktreeBranchByTaskId?.[task.id]}
              dragHandlers={getDragHandlers(task.id)}
              onEditTask={onEditTask}
            />
          ))}
        </div>
      ) : (
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
                worktreeBranch={worktreeBranchByTaskId?.[task.id]}
                sessionStatus={sessionStatusByTaskId?.[task.id]}
                worktreesForRepo={worktreesForRepo}
                onLaunchAgent={onLaunchAgent}
                onOpenSessionPicker={onOpenSessionPicker}
              />
            </div>
          ))}
          {/* Trailing insert line (drop at end) */}
          <div
            className={`insert-line${activeBeforeTaskId === null && tasks.length > 0 ? ' visible' : ''}`}
            data-before-task="__end__"
          />
        </div>
      )}

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
