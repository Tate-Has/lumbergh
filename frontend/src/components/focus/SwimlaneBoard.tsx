import { useCallback, useEffect, useRef } from 'react'
import SwimlaneRow from './SwimlaneRow'
import { STATUSES_KANBAN, WIP_LIMITS, KANBAN_LABELS } from '../../types/focusConstants'
import type { Task } from '../../types/focus'

interface SwimlaneBoardProps {
  tasks: Task[]
  swimlaneOrder: string[]
  onEditTask: (task: Task) => void
  onPromoteToday: (taskId: string) => void
  onDropTask: (taskId: string, status: string, project: string) => void
  onReorderSwimlane: (sourceProject: string, targetProject: string) => void
  onUpdateSwimlaneOrder: (order: string[]) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  taskMatchesFilters: (task: Task) => boolean
}

export default function SwimlaneBoard({
  tasks,
  swimlaneOrder,
  onEditTask,
  onPromoteToday,
  onDropTask,
  onReorderSwimlane,
  onUpdateSwimlaneOrder,
  getDragHandlers,
  taskMatchesFilters,
}: SwimlaneBoardProps) {
  const boardRef = useRef<HTMLDivElement>(null)

  // -----------------------------------------------------------------------
  // Filter to kanban tasks that match current filters
  // -----------------------------------------------------------------------

  const kanbanTasks = tasks.filter(
    (t) => (STATUSES_KANBAN as readonly string[]).includes(t.status) && taskMatchesFilters(t)
  )

  // -----------------------------------------------------------------------
  // Build sorted project list
  // -----------------------------------------------------------------------

  const projectSet = new Set<string>()
  for (const t of kanbanTasks) projectSet.add(t.project || '')

  const projects = [...projectSet].sort((a, b) => {
    const ai = swimlaneOrder.indexOf(a)
    const bi = swimlaneOrder.indexOf(b)
    if (ai !== -1 && bi !== -1) return ai - bi
    if (ai !== -1) return -1
    if (bi !== -1) return 1
    if (!a) return 1
    if (!b) return -1
    return a.localeCompare(b)
  })

  // Notify parent of the computed order so it can persist
  const prevOrderRef = useRef<string>(JSON.stringify(swimlaneOrder))
  const newOrderStr = JSON.stringify(projects)

  useEffect(() => {
    if (newOrderStr !== prevOrderRef.current) {
      prevOrderRef.current = newOrderStr
      onUpdateSwimlaneOrder(projects)
    }
  }, [newOrderStr, onUpdateSwimlaneOrder, projects])

  // -----------------------------------------------------------------------
  // Swimlane row reorder DnD
  // -----------------------------------------------------------------------

  const draggingProjectRef = useRef<string | null>(null)

  const makeRowDragStart = useCallback(
    (project: string) => (e: React.DragEvent) => {
      e.stopPropagation()
      e.dataTransfer.setData('text/swimlane-project', project)
      e.dataTransfer.effectAllowed = 'move'
      draggingProjectRef.current = project
      // Add dragging class after a tick so the browser captures the drag image first
      requestAnimationFrame(() => {
        const row = (e.target as HTMLElement).closest('.swimlane-row')
        row?.classList.add('dragging-row')
      })
    },
    []
  )

  const makeRowDragOver = useCallback(
    (_project: string) => (e: React.DragEvent) => {
      if (!e.dataTransfer.types.includes('text/swimlane-project')) return
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
      // Highlight this row
      boardRef.current
        ?.querySelectorAll('.drag-over-row')
        .forEach((r) => r.classList.remove('drag-over-row'))
      const row = (e.currentTarget as HTMLElement).closest('.swimlane-row')
      row?.classList.add('drag-over-row')
    },
    []
  )

  const makeRowDragLeave = useCallback(
    () => (e: React.DragEvent) => {
      const row = (e.currentTarget as HTMLElement).closest('.swimlane-row')
      if (row && !row.contains(e.relatedTarget as Node)) {
        row.classList.remove('drag-over-row')
      }
    },
    []
  )

  const makeRowDrop = useCallback(
    (targetProject: string) => (e: React.DragEvent) => {
      const draggedProject = e.dataTransfer.getData('text/swimlane-project')
      if (draggedProject === undefined || draggedProject === null) return
      e.preventDefault()
      e.stopPropagation()

      boardRef.current
        ?.querySelectorAll('.drag-over-row')
        .forEach((r) => r.classList.remove('drag-over-row'))
      boardRef.current
        ?.querySelectorAll('.dragging-row')
        .forEach((r) => r.classList.remove('dragging-row'))

      if (draggedProject !== targetProject) {
        onReorderSwimlane(draggedProject, targetProject)
      }
      draggingProjectRef.current = null
    },
    [onReorderSwimlane]
  )

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="swimlane-board flex flex-col gap-3" ref={boardRef}>
      {/* Header row with status column labels */}
      <div className="swimlane-header-row flex gap-3 pl-[120px] mb-1">
        {STATUSES_KANBAN.map((status) => {
          const colCount = kanbanTasks.filter((t) => t.status === status).length
          const wipLimit = WIP_LIMITS[status]
          const isOverWip = wipLimit != null && colCount > wipLimit

          return (
            <div
              key={status}
              className="swimlane-col-label flex-1 min-w-[160px] text-[0.72rem] font-semibold text-text-muted uppercase tracking-[0.04em] text-center"
            >
              {KANBAN_LABELS[status]}{' '}
              <span
                className={`col-count text-[0.7rem] font-semibold text-text-muted bg-bg-elevated rounded-lg px-[7px] py-px${isOverWip ? ' wip-over !bg-priority-high-bg !text-priority-high' : ''}`}
              >
                {colCount}
                {wipLimit != null ? `/${wipLimit}` : ''}
              </span>
            </div>
          )
        })}
      </div>

      {/* One row per project */}
      {projects.map((project) => {
        const projectTasks = kanbanTasks.filter((t) => (t.project || '') === project)

        return (
          <SwimlaneRow
            key={project || '__no_project__'}
            project={project}
            tasks={projectTasks}
            onEditTask={onEditTask}
            onPromoteToday={onPromoteToday}
            onDropTask={onDropTask}
            getDragHandlers={getDragHandlers}
            onDragStart={makeRowDragStart(project)}
            onDragOver={makeRowDragOver(project)}
            onDragLeave={makeRowDragLeave()}
            onDrop={makeRowDrop(project)}
          />
        )
      })}
    </div>
  )
}
