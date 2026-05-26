import { useCallback } from 'react'
import BoardColumn from './BoardColumn'
import SwimlaneBoard from './SwimlaneBoard'
import { STATUSES_KANBAN, WIP_LIMITS, KANBAN_LABELS } from '../../types/focusConstants'
import type { Task } from '../../types/focus'

interface TaskBoardProps {
  tasks: Task[]
  swimlaneMode: boolean
  onToggleSwimlane: () => void
  boardCollapsed: boolean
  onToggleBoardCollapsed: () => void
  backlogCollapsed: boolean
  onToggleBacklogCollapsed: () => void
  doneCollapsed: boolean
  onToggleDoneCollapsed: () => void
  onEditTask: (task: Task) => void
  onAddTask: (status: string) => void
  onPromoteToday: (taskId: string) => void
  onArchiveDone: () => void
  onDropTask: (taskId: string, status: string, beforeTaskId: string | null) => void
  onDropSwimlane: (taskId: string, status: string, project: string) => void
  onReorderSwimlane: (sourceProject: string, targetProject: string) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  taskMatchesFilters: (task: Task) => boolean
  swimlaneOrder: string[]
  onUpdateSwimlaneOrder: (order: string[]) => void
  filterDropdowns: React.ReactNode
  boardRef?: React.RefObject<HTMLDivElement | null>
}

export default function TaskBoard({
  tasks,
  swimlaneMode,
  onToggleSwimlane,
  boardCollapsed,
  onToggleBoardCollapsed,
  backlogCollapsed,
  onToggleBacklogCollapsed,
  doneCollapsed,
  onToggleDoneCollapsed,
  onEditTask,
  onAddTask,
  onPromoteToday,
  onArchiveDone,
  onDropTask,
  onDropSwimlane,
  onReorderSwimlane,
  getDragHandlers,
  taskMatchesFilters,
  swimlaneOrder,
  onUpdateSwimlaneOrder,
  filterDropdowns,
  boardRef,
}: TaskBoardProps) {
  // -----------------------------------------------------------------------
  // Header click: toggle board collapsed, but NOT when clicking buttons
  // -----------------------------------------------------------------------

  const handleHeaderClick = useCallback(
    (e: React.MouseEvent) => {
      const target = e.target as HTMLElement
      if (
        target.closest('button') ||
        target.closest('.board-filters') ||
        target.closest('select')
      ) {
        return
      }
      onToggleBoardCollapsed()
    },
    [onToggleBoardCollapsed]
  )

  const handleSwimlaneToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onToggleSwimlane()
    },
    [onToggleSwimlane]
  )

  // -----------------------------------------------------------------------
  // Build column data for the standard board view
  // -----------------------------------------------------------------------

  const renderColumns = () =>
    STATUSES_KANBAN.map((status) => {
      const colTasks = tasks.filter((t) => t.status === status)
      const visibleTasks = colTasks.filter((t) => taskMatchesFilters(t))
      const isBacklog = status === 'backlog'
      const isWaiting = status === 'waiting'
      const isDone = status === 'done'

      const isCollapsed = (isBacklog && backlogCollapsed) || (isDone && doneCollapsed)

      return (
        <BoardColumn
          key={status}
          status={status}
          label={KANBAN_LABELS[status] || status}
          tasks={visibleTasks}
          isCollapsed={isCollapsed}
          onToggleCollapse={
            isBacklog ? onToggleBacklogCollapsed : isDone ? onToggleDoneCollapsed : undefined
          }
          wipLimit={WIP_LIMITS[status]}
          isDone={isDone}
          isWaiting={isWaiting}
          isBacklog={isBacklog}
          onEditTask={onEditTask}
          onAddTask={() => onAddTask(status)}
          onPromoteToday={onPromoteToday}
          onArchiveDone={isDone ? onArchiveDone : undefined}
          onDropTask={onDropTask}
          getDragHandlers={getDragHandlers}
        />
      )
    })

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div
      className="board-section shrink-0 bg-bg-elevated border border-border-subtle rounded-xl p-5 shadow-sm overflow-hidden transition-[max-height] duration-300 ease-in-out"
      id="boardSection"
      ref={boardRef}
    >
      <div
        className={`board-header-row flex items-center justify-between${!boardCollapsed ? ' mb-4' : ''}`}
        id="boardHeaderRow"
        onClick={handleHeaderClick}
      >
        <div className="flex items-center gap-2">
          <span className="section-title text-[0.85rem] font-semibold text-text-secondary uppercase tracking-[0.04em]">
            Task Board
          </span>
          <span
            className={`board-chevron text-xs text-text-muted transition-transform duration-200 ease-in-out ml-1.5${!boardCollapsed ? ' rotate-180' : ''}`}
          >
            {boardCollapsed ? '\u25B6' : '\u25BC'}
          </span>
          <button
            className="topbar-btn"
            id="swimlaneToggle"
            title="Toggle swimlane view"
            onClick={handleSwimlaneToggle}
          >
            Swimlanes
          </button>
        </div>
        <div className="board-filters flex items-center gap-2">{filterDropdowns}</div>
      </div>

      {!boardCollapsed && (
        <div className="board-body">
          {swimlaneMode ? (
            <div className="board-columns block" id="boardColumns">
              <SwimlaneBoard
                tasks={tasks}
                swimlaneOrder={swimlaneOrder}
                onEditTask={onEditTask}
                onPromoteToday={onPromoteToday}
                onDropTask={onDropSwimlane}
                onReorderSwimlane={onReorderSwimlane}
                onUpdateSwimlaneOrder={onUpdateSwimlaneOrder}
                getDragHandlers={getDragHandlers}
                taskMatchesFilters={taskMatchesFilters}
              />
            </div>
          ) : (
            <div className="board-columns flex gap-3.5 overflow-x-auto pb-2" id="boardColumns">
              {renderColumns()}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
