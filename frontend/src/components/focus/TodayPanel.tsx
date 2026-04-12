import { useRef, useCallback } from 'react'
import type { Task, PomodoroState } from '../../types/focus'
import TodayCard from './TodayCard'
import { useTodayDragDrop } from '../../hooks/useTodayDragDrop'

interface TodayPanelProps {
  tasks: Task[]
  pomo: PomodoroState
  onToggleComplete: (taskId: string) => void
  onStartPomo: (taskId: string) => void
  onLaunchSession: (task: Task) => void
  onEditTask: (task: Task) => void
  onAddTask: () => void
  onDropTask: (taskId: string, beforeTaskId: string | null) => void
  sessionStatusMap: Record<string, { color: string; pulse: boolean; label: string }>
  onDetachSession: (taskId: string) => void
  dragHandlers: {
    getDragHandlers: (taskId: string) => {
      draggable: boolean
      onDragStart: (e: React.DragEvent) => void
      onDragEnd: (e: React.DragEvent) => void
    }
    getDropZoneHandlers: (onDrop: (taskId: string) => void) => {
      onDragOver: (e: React.DragEvent) => void
      onDragLeave: (e: React.DragEvent) => void
      onDrop: (e: React.DragEvent) => void
    }
  }
  panelRef?: React.RefObject<HTMLDivElement | null>
}

export default function TodayPanel({
  tasks,
  pomo,
  onToggleComplete,
  onStartPomo,
  onLaunchSession,
  onEditTask,
  onAddTask,
  onDropTask,
  sessionStatusMap,
  onDetachSession,
  dragHandlers,
  panelRef,
}: TodayPanelProps) {
  const gridRef = useRef<HTMLDivElement>(null)

  const todayTasks = tasks.filter((t) => t.status === 'today')
  const activeCount = todayTasks.filter((t) => !t.completed).length

  const handlePanelDrop = useCallback((taskId: string) => onDropTask(taskId, null), [onDropTask])

  const panelDropZone = dragHandlers.getDropZoneHandlers(handlePanelDrop)

  const { containerProps, indicatorGap, indicatorVisible } = useTodayDragDrop(gridRef, onDropTask)

  function isPomActive(task: Task): boolean {
    return (
      pomo.active &&
      (pomo.taskId === task.id || (!!pomo.taskTitle && pomo.taskTitle === task.title))
    )
  }

  return (
    <div
      className="panel bg-bg-elevated border border-border-subtle rounded-xl p-5 shadow-sm"
      id="todayPanel"
      ref={panelRef}
      {...panelDropZone}
    >
      <div className="section-header flex items-center justify-between mb-3.5">
        <div className="flex items-center">
          <span className="section-title text-[0.85rem] font-semibold text-text-secondary uppercase tracking-[0.04em]">
            Today
          </span>
          <span className="section-count text-xs font-semibold text-text-muted bg-bg-surface rounded-[10px] px-2.5 py-0.5 ml-2.5">
            {activeCount}
          </span>
        </div>
        <div className="section-actions flex gap-1.5">
          <button
            className="topbar-btn"
            id="addTodayBtn"
            title="Add task to today"
            onClick={onAddTask}
          >
            + Add
          </button>
        </div>
      </div>

      <div
        className="today-grid relative grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3"
        id="todayGrid"
        ref={gridRef}
        {...containerProps}
      >
        {todayTasks.length === 0 ? (
          <div className="empty-state text-[0.8rem] text-text-muted text-center p-5 italic">
            No tasks for today. Pull from the board or inbox.
          </div>
        ) : (
          todayTasks.map((task) => (
            <TodayCard
              key={task.id}
              task={task}
              isPomActive={isPomActive(task)}
              dragHandlers={dragHandlers.getDragHandlers(task.id)}
              onToggleComplete={() => onToggleComplete(task.id)}
              onStartPomo={() => onStartPomo(task.id)}
              onLaunchSession={() => onLaunchSession(task)}
              onEdit={() => onEditTask(task)}
              sessionStatus={sessionStatusMap[task.session_name]}
              onDetachSession={() => onDetachSession(task.id)}
            />
          ))
        )}

        {indicatorVisible && indicatorGap && (
          <div
            className="today-insert-indicator absolute w-[3px] bg-accent rounded-sm pointer-events-none transition-all duration-150 z-10 opacity-100"
            style={{
              left: indicatorGap.left,
              top: indicatorGap.top,
              height: indicatorGap.height,
            }}
          />
        )}
      </div>
    </div>
  )
}
