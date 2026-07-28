import { memo, useState } from 'react'
import SubtaskProgress from './SubtaskProgress'
import type { Task } from '../../types/focus'
import type { SessionStatusInfo } from '../../hooks/useSessionStatus'
import type { Worktree } from '../../hooks/useWorktrees'
import type { LaunchAgentChoice } from './LaunchAgentForm'

interface KanbanCardProps {
  task: Task
  isWaiting: boolean
  isDone: boolean
  dragHandlers: {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  onEdit: () => void
  /** Branch name of the worktree the task's linked session is running in, if any. */
  worktreeBranch?: string
  /** Live status of the task's linked session, if it has one. */
  sessionStatus?: SessionStatusInfo
  /** Worktrees available for this task's repo, for the inline launch-agent mini-form. */
  worktreesForRepo?: Worktree[]
  onLaunchAgent?: (taskId: string, choice: LaunchAgentChoice) => void
  onOpenSessionPicker?: (task: Task) => void
  /** Navigate to the task's linked session terminal, when it has a live session. */
  onViewSession?: (task: Task) => void
}

/**
 * Maps a session status color onto the existing `.session-status.<keyword>`
 * CSS modifier classes (index.css) so we reuse the established pulsing-dot
 * styling instead of inventing new animation CSS.
 */
function statusClassForColor(color: string): string {
  switch (color) {
    case 'green':
      return 'working'
    case 'yellow':
      return 'idle'
    case 'red':
      return 'error'
    default:
      return 'unknown'
  }
}

function isLiveSession(sessionStatus: SessionStatusInfo | undefined): boolean {
  return !!sessionStatus && sessionStatus.color !== 'gray' && sessionStatus.color !== 'red'
}

const KanbanCard = memo(function KanbanCard({
  task,
  isWaiting,
  isDone,
  dragHandlers,
  onEdit,
  worktreeBranch,
  sessionStatus,
  worktreesForRepo,
  onLaunchAgent,
  onOpenSessionPicker,
  onViewSession,
}: KanbanCardProps) {
  const [launchFormOpen, setLaunchFormOpen] = useState(false)
  const [selectedWorktree, setSelectedWorktree] = useState('')
  const [newBranch, setNewBranch] = useState('')

  const canLaunchAgent = task.status !== 'done' && task.status !== 'inbox'

  const handleClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.kanban-card-actions')) return
    if (isLiveSession(sessionStatus) && onViewSession) {
      onViewSession(task)
      return
    }
    onEdit()
  }

  const resetLaunchForm = () => {
    setLaunchFormOpen(false)
    setSelectedWorktree('')
    setNewBranch('')
  }

  const handleLaunchClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setLaunchFormOpen(true)
  }

  const handleOpenSessionPickerClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onOpenSessionPicker?.(task)
  }

  const handleLaunchSubmit = (e: React.MouseEvent) => {
    e.stopPropagation()
    onLaunchAgent?.(task.id, {
      worktreePath: selectedWorktree || undefined,
      newBranch: selectedWorktree ? undefined : newBranch.trim() || undefined,
    })
    resetLaunchForm()
  }

  const handleLaunchCancel = (e: React.MouseEvent) => {
    e.stopPropagation()
    resetLaunchForm()
  }

  return (
    <div
      className={`kanban-card group bg-bg-surface border border-border-default rounded-lg px-3 py-2.5 shadow-card transition-all duration-150 ease-in-out relative hover:border-accent hover:shadow-card-hover ${isWaiting ? ' waiting-card border-l-[3px] border-l-status-waiting' : ''}${isDone ? ' opacity-done' : ''}`}
      draggable={dragHandlers.draggable}
      onDragStart={dragHandlers.onDragStart}
      onDragEnd={dragHandlers.onDragEnd}
      data-task-id={task.id}
      onClick={handleClick}
    >
      <div className="kanban-card-title text-[0.92rem] font-semibold text-text-primary mb-1.5 pr-6">
        {task.title}
      </div>
      <div className="kanban-card-bottom flex items-center gap-2 flex-wrap">
        {task.project && (
          <span className="kanban-card-project text-[0.82rem] font-medium text-accent">
            {task.project}
          </span>
        )}
        <span
          className={`priority-badge text-[0.76rem] font-bold px-1.5 py-px rounded-lg uppercase tracking-[0.03em] ${task.priority === 'high' ? ' bg-priority-high-bg text-priority-high' : task.priority === 'med' ? ' bg-priority-med-bg text-priority-med' : ' bg-priority-low-bg text-priority-low'}`}
        >
          {task.priority}
        </span>
        {worktreeBranch && (
          <span className="kanban-card-worktree text-[0.76rem] font-mono text-purple bg-purple/10 border border-purple/20 rounded px-1.5 py-px truncate max-w-[9rem]">
            {worktreeBranch}
          </span>
        )}
      </div>
      {task.blocker && (
        <div className="kanban-card-blocker text-[0.85rem] text-status-waiting mt-1 font-medium">
          &#x23F3; {task.blocker}
        </div>
      )}
      <SubtaskProgress subtasks={task.subtasks} />

      {sessionStatus ? (
        <div
          className={`session-status ${statusClassForColor(sessionStatus.color)} flex items-center gap-1.5 mt-1.5 text-[0.82rem]`}
        >
          <span className="session-dot w-2 h-2 rounded-full shrink-0" />
          <span className="font-semibold shrink-0">{sessionStatus.label}</span>
          {task.check_in_note && (
            <span className="text-text-muted truncate">{task.check_in_note}</span>
          )}
        </div>
      ) : (
        canLaunchAgent && (
          <div className="kanban-card-actions mt-1.5" onClick={(e) => e.stopPropagation()}>
            {launchFormOpen ? (
              <div className="flex flex-col gap-1.5">
                <select
                  className="w-full text-[0.85rem] px-1.5 py-1 rounded-md border border-border-default bg-bg-elevated text-text-primary outline-none focus:border-accent"
                  value={selectedWorktree}
                  onChange={(e) => setSelectedWorktree(e.target.value)}
                >
                  <option value="">New branch&hellip;</option>
                  {(worktreesForRepo || []).map((wt) => (
                    <option key={wt.path} value={wt.path}>
                      {wt.branch}
                      {wt.is_main ? ' (main)' : ''}
                    </option>
                  ))}
                </select>
                {!selectedWorktree && (
                  <input
                    type="text"
                    placeholder="new-branch-name"
                    value={newBranch}
                    onChange={(e) => setNewBranch(e.target.value)}
                    className="w-full text-[0.85rem] px-1.5 py-1 rounded-md border border-border-default bg-bg-elevated text-text-primary outline-none focus:border-accent"
                  />
                )}
                <div className="flex gap-1.5">
                  <button
                    className="flex-1 text-[0.76rem] font-semibold px-2 py-1 rounded-md border border-status-running text-status-running bg-status-running-bg cursor-pointer transition-all duration-100 hover:opacity-80"
                    onClick={handleLaunchSubmit}
                  >
                    Launch
                  </button>
                  <button
                    className="text-[0.76rem] font-semibold px-2 py-1 rounded-md border border-border-default text-text-secondary bg-bg-elevated cursor-pointer transition-all duration-100 hover:border-accent hover:text-accent"
                    onClick={handleLaunchCancel}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  className="kanban-launch-btn text-[0.8rem] font-semibold px-2 py-0.5 rounded-md border border-status-running text-status-running bg-transparent cursor-pointer transition-all duration-150 ease-in-out hover:bg-status-running-bg"
                  onClick={handleLaunchClick}
                >
                  &#9654; Launch agent
                </button>
                <button
                  className="kanban-session-picker-btn text-[0.8rem] text-text-muted cursor-pointer transition-colors duration-150 hover:text-accent"
                  title="Link existing session"
                  onClick={handleOpenSessionPickerClick}
                >
                  &#x1F517;
                </button>
              </div>
            )}
          </div>
        )
      )}
    </div>
  )
})

export default KanbanCard
