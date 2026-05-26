import KanbanCard from './KanbanCard'
import { STATUSES_KANBAN } from '../../types/focusConstants'
import type { Task } from '../../types/focus'

interface SwimlaneRowProps {
  project: string
  tasks: Task[] // tasks for this project (already filtered to kanban statuses)
  onEditTask: (task: Task) => void
  onPromoteToday: (taskId: string) => void
  onDropTask: (taskId: string, status: string, project: string) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  // Swimlane row drag reorder handlers
  onDragStart: (e: React.DragEvent) => void
  onDragOver: (e: React.DragEvent) => void
  onDragLeave: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent) => void
}

export default function SwimlaneRow({
  project,
  tasks,
  onEditTask,
  onPromoteToday,
  onDropTask,
  getDragHandlers,
  onDragStart,
  onDragOver,
  onDragLeave,
  onDrop,
}: SwimlaneRowProps) {
  const handleCellDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  const handleCellDrop = (e: React.DragEvent, status: string) => {
    e.preventDefault()
    e.stopPropagation()
    const taskId = e.dataTransfer.getData('text/plain')
    if (taskId) {
      onDropTask(taskId, status, project)
    }
  }

  return (
    <div
      className="swimlane-row flex gap-3 items-stretch"
      data-project={project}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div className="swimlane-label w-[108px] shrink-0 flex items-center justify-end pr-3">
        <span className="drag-handle" draggable onDragStart={onDragStart}>
          &#x2807;
        </span>
        <span
          className={`swimlane-label-text text-[0.78rem] font-semibold text-accent whitespace-nowrap overflow-hidden text-ellipsis${!project ? ' no-project !text-text-muted italic' : ''}`}
        >
          {project || 'No project'}
        </span>
        <span className="swimlane-row-count text-[0.65rem] font-semibold text-text-muted bg-bg-surface rounded-lg px-[5px] py-px ml-1">
          {tasks.length}
        </span>
      </div>

      <div className="swimlane-cells flex gap-3 flex-1 min-h-[50px]">
        {STATUSES_KANBAN.map((status) => {
          const isWaiting = status === 'waiting'
          const isDone = status === 'done'
          const cellTasks = tasks.filter((t) => t.status === status)

          return (
            <div
              key={status}
              className={`swimlane-cell flex-1 min-w-[160px] bg-bg-surface rounded-lg p-2 flex flex-col gap-1.5 min-h-[40px] ${isWaiting ? ' waiting-cell bg-waiting-col-bg' : ''}${isDone ? ' done-cell' : ''}`}
              data-status={status}
              data-project={project}
              onDragOver={handleCellDragOver}
              onDrop={(e) => handleCellDrop(e, status)}
            >
              {cellTasks.map((task) => (
                <KanbanCard
                  key={task.id}
                  task={task}
                  isWaiting={isWaiting}
                  isDone={isDone}
                  dragHandlers={getDragHandlers(task.id)}
                  onEdit={() => onEditTask(task)}
                  onPromoteToday={() => onPromoteToday(task.id)}
                />
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
