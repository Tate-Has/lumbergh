import type { SubTask } from '../../types/focus'

interface SubtaskProgressProps {
  subtasks: SubTask[]
}

export default function SubtaskProgress({ subtasks }: SubtaskProgressProps) {
  if (!subtasks || subtasks.length === 0) return null

  const done = subtasks.filter((s) => s.done).length
  const total = subtasks.length
  const pct = Math.round((done / total) * 100)

  return (
    <div className="subtask-progress flex items-center gap-1.5 mt-1.5 text-[0.7rem] text-text-secondary">
      <div className="subtask-bar flex-1 h-1 bg-border-default rounded-sm overflow-hidden">
        <div
          className="subtask-bar-fill h-full bg-accent rounded-sm transition-[width] duration-200 ease-in-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="subtask-count whitespace-nowrap min-w-6 text-right">
        {done}/{total}
      </span>
    </div>
  )
}
