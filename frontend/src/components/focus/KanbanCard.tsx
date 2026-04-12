import { memo } from 'react'
import SubtaskProgress from './SubtaskProgress'
import type { Task } from '../../types/focus'

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
  onPromoteToday: () => void
}

const KanbanCard = memo(function KanbanCard({
  task,
  isWaiting,
  isDone,
  dragHandlers,
  onEdit,
  onPromoteToday,
}: KanbanCardProps) {
  const handlePromote = (e: React.MouseEvent) => {
    e.stopPropagation()
    onPromoteToday()
  }

  const handleClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.kanban-promote-btn')) return
    onEdit()
  }

  return (
    <div
      className={`kanban-card group bg-bg-elevated border border-border-subtle rounded-lg px-3 py-2.5 transition-all duration-150 ease-in-out relative hover:border-accent hover:shadow-card-hover ${isWaiting ? ' waiting-card border-l-[3px] border-l-status-waiting' : ''}${isDone ? ' opacity-done' : ''}`}
      draggable={dragHandlers.draggable}
      onDragStart={dragHandlers.onDragStart}
      onDragEnd={dragHandlers.onDragEnd}
      data-task-id={task.id}
      onClick={handleClick}
    >
      {!isDone && (
        <button
          className="kanban-promote-btn absolute top-[7px] right-[7px] bg-bg-surface border border-border-default rounded-[5px] px-1.5 py-px text-[0.65rem] font-semibold text-accent cursor-pointer opacity-0 transition-all duration-150 ease-in-out group-hover:opacity-100 hover:bg-orange-subtle hover:border-accent"
          data-task-id={task.id}
          onClick={handlePromote}
        >
          &rarr; today
        </button>
      )}
      <div className="kanban-card-title text-[0.8rem] font-semibold text-text-primary mb-1.5 pr-6">
        {task.title}
      </div>
      <div className="kanban-card-bottom flex items-center gap-2">
        {task.project && (
          <span className="kanban-card-project text-[0.7rem] font-medium text-accent">
            {task.project}
          </span>
        )}
        <span
          className={`priority-badge text-[0.65rem] font-bold px-1.5 py-px rounded-lg uppercase tracking-[0.03em] ${task.priority === 'high' ? ' bg-priority-high-bg text-priority-high' : task.priority === 'med' ? ' bg-priority-med-bg text-priority-med' : ' bg-priority-low-bg text-priority-low'}`}
        >
          {task.priority}
        </span>
      </div>
      {task.blocker && (
        <div className="kanban-card-blocker text-[0.72rem] text-status-waiting mt-1 font-medium">
          &#x23F3; {task.blocker}
        </div>
      )}
      <SubtaskProgress subtasks={task.subtasks} />
    </div>
  )
})

export default KanbanCard
