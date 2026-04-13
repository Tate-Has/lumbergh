import { memo, useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Task } from '../../types/focus'
import SubtaskProgress from './SubtaskProgress'
import { statusColorClasses } from '../../utils/sessionStatus'

const DURATION_PRESETS = [
  { label: '15m', seconds: 15 * 60 },
  { label: '25m', seconds: 25 * 60 },
  { label: '45m', seconds: 45 * 60 },
  { label: '60m', seconds: 60 * 60 },
]

interface TodayCardProps {
  task: Task
  isPomActive: boolean
  dragHandlers: {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  onToggleComplete: () => void
  onStartPomo: (durationSeconds?: number) => void
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
  const [pickerOpen, setPickerOpen] = useState(false)
  const [customMin, setCustomMin] = useState('')
  const pickerRef = useRef<HTMLDivElement>(null)

  // Close picker on outside click
  useEffect(() => {
    if (!pickerOpen) return
    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerOpen(false)
        setCustomMin('')
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [pickerOpen])

  function startWithDuration(seconds: number) {
    setPickerOpen(false)
    setCustomMin('')
    onStartPomo(seconds)
  }

  function handleCustomStart() {
    const mins = parseInt(customMin, 10)
    if (mins > 0) startWithDuration(mins * 60)
  }

  const cardClass =
    `today-card group bg-bg-surface border border-border-subtle rounded-lg px-3.5 pt-3 pb-8 min-h-[72px] cursor-pointer transition-all duration-150 relative hover:border-accent hover:shadow-card-hover hover:-translate-y-px` +
    (task.completed ? ' completed' : '') +
    (isPomActive ? ' pomo-active' : '')

  function handleCardClick(e: React.MouseEvent) {
    const target = e.target as HTMLElement
    if (
      target.closest('.check-icon') ||
      target.closest('.today-card-pomo') ||
      target.closest('.pomo-duration-picker') ||
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
      <div className="absolute bottom-2 left-2">
        <button
          className="today-card-pomo w-[22px] h-[22px] border border-border-default rounded-full bg-transparent text-text-muted text-[0.6rem] cursor-pointer flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-150 hover:border-accent hover:text-accent hover:bg-orange-subtle"
          title="Start focus timer"
          onClick={(e) => {
            e.stopPropagation()
            setPickerOpen((v) => !v)
          }}
        >
          {'\u25B6'}
        </button>
        {pickerOpen && (
          <div
            ref={pickerRef}
            className="pomo-duration-picker absolute bottom-full left-0 mb-1.5 bg-bg-elevated border border-border-default rounded-lg shadow-lg p-2 z-20 min-w-[140px]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-[0.65rem] text-text-muted uppercase tracking-wide mb-1.5 px-0.5">
              Focus duration
            </div>
            <div className="grid grid-cols-2 gap-1 mb-1.5">
              {DURATION_PRESETS.map((p) => (
                <button
                  key={p.seconds}
                  className="text-[0.75rem] font-semibold px-2 py-1 rounded-md border border-border-subtle bg-bg-surface text-text-primary cursor-pointer transition-all duration-100 hover:border-accent hover:text-accent hover:bg-orange-subtle"
                  onClick={() => startWithDuration(p.seconds)}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="flex gap-1">
              <input
                type="number"
                min="1"
                max="180"
                placeholder="min"
                value={customMin}
                onChange={(e) => setCustomMin(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCustomStart()
                }}
                className="flex-1 min-w-0 text-[0.72rem] px-1.5 py-1 rounded-md border border-border-subtle bg-bg-surface text-text-primary outline-none focus:border-accent"
              />
              <button
                className="text-[0.65rem] font-semibold px-2 py-1 rounded-md border border-border-subtle bg-bg-surface text-text-muted cursor-pointer transition-all duration-100 hover:border-accent hover:text-accent hover:bg-orange-subtle disabled:opacity-40 disabled:cursor-default"
                disabled={!customMin || parseInt(customMin, 10) <= 0}
                onClick={handleCustomStart}
              >
                Go
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
})
