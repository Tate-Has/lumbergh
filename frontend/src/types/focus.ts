export interface SubTask {
  text: string
  done: boolean
}

export interface Task {
  id: string
  title: string
  project: string
  priority: 'high' | 'med' | 'low'
  status: string
  blocker: string
  check_in_note: string
  completed: boolean
  completed_date: string
  session_name: string
  session_status: string
  subtasks: SubTask[]
}

export interface PriorityFilters {
  high: boolean
  med: boolean
  low: boolean
}

export interface PomodoroState {
  active: boolean
  running: boolean
  taskId: string | null
  taskTitle: string
  phase: 'work' | 'break'
  remaining: number
  intervalId: ReturnType<typeof setInterval> | null
}

export interface TouchDragState {
  active: boolean
  ghost: HTMLElement | null
  sourceEl: HTMLElement | null
  taskId: string | null
  longPressTimer: ReturnType<typeof setTimeout> | null
  currentDropZone: HTMLElement | null
  isSwimlaneRow: boolean
  startX: number
  startY: number
  scrollThreshold: number
  offsetX: number
  offsetY: number
}

export type SessionStatus = 'working' | 'idle' | 'error' | 'stalled' | 'unknown'
