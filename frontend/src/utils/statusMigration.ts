import type { Task } from '../types/focus'
import { STATUSES_KANBAN } from '../types/focusConstants'

const KANBAN_STATUS_SET = new Set<string>(STATUSES_KANBAN)

/**
 * Pure, render-only projection of a task's legacy/free-form status onto the
 * fixed set of Kanban board columns. Never mutates the task or persists anything.
 */
export function resolveBoardStatus(task: Task): (typeof STATUSES_KANBAN)[number] {
  if (task.status === 'today') return 'backlog'

  if (task.status === 'running') {
    return task.session_name ? 'in-progress' : 'backlog'
  }

  if (KANBAN_STATUS_SET.has(task.status)) {
    return task.status as (typeof STATUSES_KANBAN)[number]
  }

  return 'backlog'
}
