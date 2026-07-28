import { useState, useCallback } from 'react'
import BoardColumn from './BoardColumn'
import { STATUSES_KANBAN, WIP_LIMITS, KANBAN_LABELS } from '../../types/focusConstants'
import { resolveBoardStatus } from '../../utils/statusMigration'
import type { Repo } from '../../utils/repos'
import type { Worktree } from '../../hooks/useWorktrees'
import type { SessionStatusInfo } from '../../hooks/useSessionStatus'
import type { Task } from '../../types/focus'
import type { LaunchAgentChoice } from './LaunchAgentForm'

interface RepoLaneProps {
  repos: Repo[]
  tasks: Task[]
  worktreesByRepo: Record<string, Worktree[]>
  worktreeBranchByTaskId: Record<string, string | undefined>
  sessionStatusByTaskId: Record<string, SessionStatusInfo | undefined>
  onEditTask: (task: Task) => void
  onAddTask: (repoId: string) => void
  onArchiveDone: (repoId: string) => void
  onDropTask: (taskId: string, status: string, beforeTaskId: string | null) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  onLaunchAgent: (taskId: string, choice: LaunchAgentChoice) => void
  onOpenSessionPicker: (task: Task) => void
  onViewSession: (task: Task) => void
  taskMatchesFilters?: (task: Task) => boolean
}

/** True if a task's linked session is alive and not offline/errored. */
function hasLiveSession(task: Task, sessionStatusByTaskId: RepoLaneProps['sessionStatusByTaskId']) {
  if (!task.session_name) return false
  const status = sessionStatusByTaskId[task.id]
  return !!status && status.color !== 'gray' && status.color !== 'red'
}

function RepoPanel({
  repo,
  tasks,
  worktreesByRepo,
  worktreeBranchByTaskId,
  sessionStatusByTaskId,
  onEditTask,
  onAddTask,
  onArchiveDone,
  onDropTask,
  getDragHandlers,
  onLaunchAgent,
  onOpenSessionPicker,
  onViewSession,
  taskMatchesFilters,
}: RepoLaneProps & { repo: Repo; tasks: Task[] }) {
  const [collapsed, setCollapsed] = useState(false)
  const [backlogCollapsed, setBacklogCollapsed] = useState(false)
  const [doneCollapsed, setDoneCollapsed] = useState(false)

  const toggleCollapsed = useCallback(() => setCollapsed((v) => !v), [])
  const toggleBacklogCollapsed = useCallback(() => setBacklogCollapsed((v) => !v), [])
  const toggleDoneCollapsed = useCallback(() => setDoneCollapsed((v) => !v), [])

  const activeCount = tasks.filter((t) => hasLiveSession(t, sessionStatusByTaskId)).length
  const worktreesForRepo = worktreesByRepo[repo.id] || []

  return (
    <div className="repo-lane bg-bg-surface border border-border-default rounded-xl p-4 shadow-card">
      <div
        className="repo-lane-header flex items-center justify-between gap-2 mb-3 cursor-pointer"
        onClick={toggleCollapsed}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`repo-lane-chevron text-sm text-text-muted transition-transform duration-200 ease-in-out${collapsed ? '' : ' rotate-90'}`}
          >
            &#x25B6;
          </span>
          <span
            className="repo-lane-dot w-2.5 h-2.5 rounded-full shrink-0"
            style={{ background: repo.color }}
          />
          <span className="repo-lane-name text-base font-semibold text-text-primary truncate">
            {repo.name}
          </span>
          {activeCount > 0 && (
            <span className="repo-lane-active-count text-[0.8rem] font-semibold text-status-running bg-status-running-bg rounded-lg px-2 py-px shrink-0">
              {activeCount} active
            </span>
          )}
        </div>
        <button
          className="repo-lane-add-btn shrink-0 text-[0.85rem] font-semibold text-accent bg-orange-subtle border border-transparent rounded-md px-2.5 py-1 cursor-pointer transition-all duration-150 ease-in-out hover:border-accent"
          onClick={(e) => {
            e.stopPropagation()
            onAddTask(repo.id)
          }}
        >
          + Task
        </button>
      </div>

      {!collapsed && (
        <div
          className="repo-lane-columns grid gap-3 overflow-x-auto"
          style={{ gridTemplateColumns: 'repeat(5, minmax(180px, 1fr))' }}
        >
          {STATUSES_KANBAN.map((status) => {
            const colTasks = tasks.filter((t) => resolveBoardStatus(t) === status)
            const visibleTasks = taskMatchesFilters ? colTasks.filter(taskMatchesFilters) : colTasks
            const isBacklog = status === 'backlog'
            const isWaiting = status === 'waiting'
            const isDone = status === 'done'

            return (
              <BoardColumn
                key={status}
                status={status}
                label={KANBAN_LABELS[status] || status}
                tasks={visibleTasks}
                isCollapsed={isDone && doneCollapsed}
                onToggleCollapse={isDone ? toggleDoneCollapsed : undefined}
                backlogCollapsed={isBacklog ? backlogCollapsed : undefined}
                onToggleBacklogCollapsed={isBacklog ? toggleBacklogCollapsed : undefined}
                wipLimit={WIP_LIMITS[status]}
                isDone={isDone}
                isWaiting={isWaiting}
                isBacklog={isBacklog}
                onEditTask={onEditTask}
                onAddTask={() => onAddTask(repo.id)}
                onArchiveDone={isDone ? () => onArchiveDone(repo.id) : undefined}
                onDropTask={onDropTask}
                getDragHandlers={getDragHandlers}
                worktreeBranchByTaskId={worktreeBranchByTaskId}
                sessionStatusByTaskId={sessionStatusByTaskId}
                worktreesForRepo={worktreesForRepo}
                onLaunchAgent={onLaunchAgent}
                onOpenSessionPicker={onOpenSessionPicker}
                onViewSession={onViewSession}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function RepoLane(props: RepoLaneProps) {
  const { repos, tasks } = props

  return (
    <div className="repo-lane-list flex flex-col gap-3">
      {repos.map((repo) => (
        <RepoPanel
          key={repo.id}
          {...props}
          repo={repo}
          tasks={tasks.filter((t) => t.project === repo.id)}
        />
      ))}
    </div>
  )
}
