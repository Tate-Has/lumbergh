import { memo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Task } from '../../types/focus'
import SubtaskProgress from './SubtaskProgress'
import { statusColorClasses } from '../../utils/sessionStatus'

interface TodayCardProps {
  task: Task
  isPomActive: boolean
  dragHandlers: {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  onToggleComplete: () => void
  onStartPomo: () => void
  onOpenSessionPicker: () => void
  onEdit: () => void
  sessionStatus?: { color: string; pulse: boolean; label: string }
  onDetachSession?: () => void
}

function SessionArea({
  task,
  sessionStatus,
  onOpenSessionPicker,
  onDetachSession,
}: {
  task: Task
  sessionStatus?: { color: string; pulse: boolean; label: string }
  onOpenSessionPicker: () => void
  onDetachSession?: () => void
}) {
  const navigate = useNavigate()

  if (task.session_name) {
    const color = sessionStatus?.color || 'gray'
    return (
      <div className="session-badge-row absolute bottom-2 right-2 flex items-center gap-1.5">
        <button
          className={`session-badge inline-flex items-center gap-[5px] text-[0.65rem] font-semibold uppercase tracking-[0.03em] cursor-pointer hover:opacity-80 transition-opacity ${statusColorClasses[color]?.text || 'text-text-tertiary'}`}
          onClick={(e) => {
            e.stopPropagation()
            navigate('/session/' + task.session_name)
          }}
          title={`Open session in Lumbergh (${sessionStatus?.label || 'Loading...'})`}
        >
          <span
            className={`session-dot w-2 h-2 rounded-full shrink-0 ${statusColorClasses[color]?.dot || 'bg-gray-500'} ${sessionStatus?.pulse ? 'animate-pulse' : ''}`}
          />
          <span className="session-label">{sessionStatus?.label || 'Loading...'}</span>
        </button>
        <button
          className="session-detach text-text-muted hover:text-red-400 text-[0.6rem] cursor-pointer transition-colors opacity-0 group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation()
            onDetachSession?.()
          }}
          title="Detach session"
        >
          ✕
        </button>
      </div>
    )
  }

  return (
    <button
      className="today-card-launch absolute bottom-2 right-2 w-[22px] h-[22px] border border-border-default rounded-full bg-transparent text-text-muted text-[0.5rem] font-bold cursor-pointer flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-150 font-mono hover:border-status-running hover:text-status-running hover:bg-status-running-bg"
      title="Launch session"
      onClick={(e) => {
        e.stopPropagation()
        onOpenSessionPicker()
      }}
    >
      {'>'}_
    </button>
  )
}

export default memo(function TodayCard({
  task,
  isPomActive,
  dragHandlers,
  onToggleComplete,
  onStartPomo,
  onOpenSessionPicker,
  onEdit,
  sessionStatus,
  onDetachSession,
}: TodayCardProps) {
  const cardClass =
    `today-card group bg-bg-surface border border-border-subtle rounded-lg px-3.5 pt-3 pb-8 min-h-[72px] cursor-pointer transition-all duration-150 relative hover:border-accent hover:shadow-card-hover hover:-translate-y-px` +
    (task.completed ? ' completed' : '') +
    (isPomActive ? ' pomo-active' : '')

  function handleCardClick(e: React.MouseEvent) {
    const target = e.target as HTMLElement
    if (
      target.closest('.check-icon') ||
      target.closest('.today-card-pomo') ||
      target.closest('.today-card-launch') ||
      target.closest('.session-badge') ||
      target.closest('.session-detach')
    ) {
      return
    }
    onEdit()
  }

  return (
    <div className={cardClass} data-task-id={task.id} onClick={handleCardClick} {...dragHandlers}>
      <div
        className="check-icon absolute top-2 right-2 w-[18px] h-[18px] border-2 border-border-default rounded-full flex items-center justify-center transition-all duration-150 shrink-0 cursor-pointer z-[2] group-hover:border-accent"
        onClick={(e) => {
          e.stopPropagation()
          onToggleComplete()
        }}
      />
      <div className="today-card-title text-[0.82rem] font-semibold text-text-primary mb-1.5 pr-6">
        {task.title}
      </div>
      {task.project && (
        <div className="today-card-project text-[0.72rem] font-medium text-accent">
          {task.project}
        </div>
      )}
      <SessionArea
        task={task}
        sessionStatus={sessionStatus}
        onOpenSessionPicker={onOpenSessionPicker}
        onDetachSession={onDetachSession}
      />
      <SubtaskProgress subtasks={task.subtasks} />
      <button
        className="today-card-pomo absolute bottom-2 left-2 w-[22px] h-[22px] border border-border-default rounded-full bg-transparent text-text-muted text-[0.6rem] cursor-pointer flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-150 hover:border-accent hover:text-accent hover:bg-orange-subtle"
        title="Start focus timer"
        onClick={(e) => {
          e.stopPropagation()
          onStartPomo()
        }}
      >
        {'\u25B6'}
      </button>
    </div>
  )
})
