import type { Task } from '../../types/focus'
import FocusSessionCard from './FocusSessionCard'

interface InFlightPanelProps {
  tasks: Task[]
  onEditTask: (task: Task) => void
  onLaunchSession: (task: Task) => void
  onUpdateCheckIn: (taskId: string, note: string) => void
  dropZoneHandlers: {
    onDragOver: (e: React.DragEvent) => void
    onDragLeave: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
  }
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
}

export default function InFlightPanel({
  tasks,
  onEditTask,
  onLaunchSession,
  onUpdateCheckIn,
  dropZoneHandlers,
  getDragHandlers,
}: InFlightPanelProps) {
  const sessionTasks = tasks.filter((t) => t.status === 'running' || t.status === 'waiting')

  return (
    <div
      className="panel bg-bg-elevated border border-border-subtle rounded-xl p-5 shadow-sm"
      id="sessionsPanel"
      {...dropZoneHandlers}
    >
      <div className="section-header flex items-center justify-between mb-3.5">
        <div className="flex items-center">
          <span className="section-title text-[0.85rem] font-semibold text-text-secondary uppercase tracking-[0.04em]">
            In Flight
          </span>
          <span className="section-count text-xs font-semibold text-text-muted bg-bg-surface rounded-[10px] px-2.5 py-0.5 ml-2.5">
            {sessionTasks.length}
          </span>
        </div>
      </div>
      <div className="sessions-list flex flex-col gap-2.5" id="sessionsList">
        {sessionTasks.length === 0 ? (
          <div className="empty-state text-[0.8rem] text-text-muted text-center p-5 italic">
            No in-flight work. Drag tasks here for ongoing background work.
          </div>
        ) : (
          sessionTasks.map((task) => (
            <FocusSessionCard
              key={task.id}
              task={task}
              dragHandlers={getDragHandlers(task.id)}
              onEdit={() => onEditTask(task)}
              onLaunchSession={() => onLaunchSession(task)}
              onUpdateCheckIn={(note) => onUpdateCheckIn(task.id, note)}
            />
          ))
        )}
      </div>
    </div>
  )
}
