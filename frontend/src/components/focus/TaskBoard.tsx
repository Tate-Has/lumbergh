import BoardColumn from './BoardColumn'
import { STATUSES_KANBAN, WIP_LIMITS, KANBAN_LABELS } from '../../types/focusConstants'
import { resolveBoardStatus } from '../../utils/statusMigration'
import type { Task } from '../../types/focus'
import type { SessionStatusInfo } from '../../hooks/useSessionStatus'
import type { LaunchAgentChoice } from './LaunchAgentForm'

interface TaskBoardProps {
  tasks: Task[]
  backlogCollapsed: boolean
  onToggleBacklogCollapsed: () => void
  doneCollapsed: boolean
  onToggleDoneCollapsed: () => void
  onEditTask: (task: Task) => void
  onAddTask: (status: string) => void
  onArchiveDone: () => void
  onDropTask: (taskId: string, status: string, beforeTaskId: string | null) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  taskMatchesFilters: (task: Task) => boolean
  worktreeBranchByTaskId?: Record<string, string | undefined>
  sessionStatusByTaskId?: Record<string, SessionStatusInfo | undefined>
  onLaunchAgent?: (taskId: string, choice: LaunchAgentChoice) => void
  onOpenSessionPicker?: (task: Task) => void
  onViewSession?: (task: Task) => void
  boardRef?: React.RefObject<HTMLDivElement | null>
}

/**
 * Flat (pooled) board — all repos' tasks in one set of five Kanban columns,
 * no per-repo grouping. This is the "Flat board" mode toggled from
 * <Toolbar>; the repo-grouped equivalent is <RepoLane>.
 *
 * Note: because columns here pool tasks across repos, the inline
 * launch-agent mini-form on each card can't offer a "pick an existing
 * worktree" dropdown scoped to that card's repo (there is no single
 * `worktreesForRepo` list that applies to every card in a column) — it
 * still supports launching with a brand-new branch name. Switch to
 * "Repo lanes" for the full existing-worktree picker.
 */
export default function TaskBoard({
  tasks,
  backlogCollapsed,
  onToggleBacklogCollapsed,
  doneCollapsed,
  onToggleDoneCollapsed,
  onEditTask,
  onAddTask,
  onArchiveDone,
  onDropTask,
  getDragHandlers,
  taskMatchesFilters,
  worktreeBranchByTaskId,
  sessionStatusByTaskId,
  onLaunchAgent,
  onOpenSessionPicker,
  onViewSession,
  boardRef,
}: TaskBoardProps) {
  const renderColumns = () =>
    STATUSES_KANBAN.map((status) => {
      const colTasks = tasks.filter((t) => resolveBoardStatus(t) === status)
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
          backlogCollapsed={isBacklog ? backlogCollapsed : undefined}
          onToggleBacklogCollapsed={isBacklog ? onToggleBacklogCollapsed : undefined}
          wipLimit={WIP_LIMITS[status]}
          isDone={isDone}
          isWaiting={isWaiting}
          isBacklog={isBacklog}
          onEditTask={onEditTask}
          onAddTask={() => onAddTask(status)}
          onArchiveDone={isDone ? onArchiveDone : undefined}
          onDropTask={onDropTask}
          getDragHandlers={getDragHandlers}
          worktreeBranchByTaskId={worktreeBranchByTaskId}
          sessionStatusByTaskId={sessionStatusByTaskId}
          onLaunchAgent={onLaunchAgent}
          onOpenSessionPicker={onOpenSessionPicker}
          onViewSession={onViewSession}
        />
      )
    })

  return (
    <div
      className="board-section shrink-0 bg-bg-elevated border border-border-subtle rounded-xl p-5 shadow-sm overflow-hidden"
      id="boardSection"
      ref={boardRef}
    >
      <div className="board-columns flex gap-3.5 overflow-x-auto pb-2" id="boardColumns">
        {renderColumns()}
      </div>
    </div>
  )
}
