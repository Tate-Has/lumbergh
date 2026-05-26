// Focus Workspace constants extracted from FocusTaskContext to satisfy
// react-refresh/only-export-components (context files must not export
// non-component/hook values alongside the provider).

export const STATUSES_KANBAN = ['backlog', 'in-progress', 'waiting', 'review', 'done'] as const
export const STATUSES_ALL = [
  'inbox',
  'today',
  'running',
  'waiting',
  'backlog',
  'in-progress',
  'review',
  'done',
] as const
export const WIP_LIMITS: Record<string, number> = { 'in-progress': 3 }
export const KANBAN_LABELS: Record<string, string> = {
  backlog: 'Backlog',
  'in-progress': 'In Progress',
  waiting: 'Waiting On',
  review: 'Review',
  done: 'Done',
}
