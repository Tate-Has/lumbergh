import { memo } from 'react'
import type { Task } from '../../types/focus'

interface SessionCardProps {
  task: Task
  dragHandlers: {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  onEdit: () => void
  onLaunchSession: () => void
  onUpdateCheckIn: (note: string) => void
}

export default memo(function SessionCard({
  task,
  dragHandlers,
  onEdit,
  onLaunchSession,
  onUpdateCheckIn,
}: SessionCardProps) {
  const handleCardClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.closest('.session-card-launch')) return
    onEdit()
  }

  const handleLaunchClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onLaunchSession()
  }

  const handleCheckInInput = (e: React.FormEvent<HTMLInputElement>) => {
    onUpdateCheckIn(e.currentTarget.value)
  }

  const sessDot =
    task.session_name && task.session_status ? (
      <span
        className={`session-status inline-flex items-center gap-[5px] text-[0.65rem] font-semibold mt-1 uppercase tracking-[0.03em] ${task.session_status}`}
      >
        <span className="session-dot w-2 h-2 rounded-full shrink-0"></span>
        <span className="session-label">{task.session_status}</span>
      </span>
    ) : null

  return (
    <div
      className="session-card bg-bg-surface border border-border-subtle rounded-lg px-3.5 py-3 transition-all duration-150 hover:border-accent hover:shadow-card-hover"
      data-task-id={task.id}
      onClick={handleCardClick}
      {...dragHandlers}
    >
      <div className="session-card-top flex items-center justify-between mb-1">
        <span className="session-card-title text-[0.82rem] font-semibold text-text-primary">
          {task.title}
        </span>
        <div className="session-card-meta flex items-center gap-2">
          {task.project && (
            <span className="session-card-project text-[0.72rem] font-medium text-accent">
              {task.project}
            </span>
          )}
          <button
            className={`session-card-launch w-5 h-5 border border-border-default rounded-full bg-transparent text-text-muted text-[0.45rem] font-bold cursor-pointer inline-flex items-center justify-center transition-all duration-150 font-mono shrink-0 hover:border-status-running hover:text-status-running hover:bg-status-running-bg${task.session_name ? ' linked !border-status-running !text-status-running' : ''}`}
            title={task.session_name ? 'Open session' : 'Launch session'}
            onClick={handleLaunchClick}
          >
            {'>'}_
          </button>
          {sessDot}
        </div>
      </div>
      <div className="session-card-checkin mt-1.5">
        <input
          className="w-full bg-bg-elevated border border-border-subtle rounded-md px-2.5 py-1.5 text-xs text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent placeholder:text-text-muted"
          type="text"
          defaultValue={task.check_in_note}
          placeholder="Check-in note..."
          data-task-id={task.id}
          onInput={handleCheckInInput}
        />
      </div>
    </div>
  )
})
