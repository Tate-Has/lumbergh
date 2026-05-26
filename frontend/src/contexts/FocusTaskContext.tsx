import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
} from 'react'
import type { Task } from '../types/focus'
import { todayISO } from '../utils/focus'
import { getApiBase } from '../config'

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface TaskContextValue {
  tasks: Task[]
  setTasks: (tasks: Task[] | ((prev: Task[]) => Task[])) => void
  addTask: (task: Task) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  deleteTask: (id: string) => void
  moveTaskToStatus: (taskId: string, newStatus: string, beforeTaskId?: string | null) => void
  reorderTasks: (reorderedTasks: Task[]) => void
  markChanged: () => void
  modalOpenRef: { current: boolean }
  showToast: (msg: string) => void
  toastMessage: string
  toastVisible: boolean
}

const TaskContext = createContext<TaskContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function TaskProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [toastMessage, setToastMessage] = useState('')
  const [toastVisible, setToastVisible] = useState(false)

  // Synchronous refs — never cause re-renders, safe to read in poll callback
  const hasPendingSaveRef = useRef(false)
  const lastChangeTimeRef = useRef(0)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const modalOpenRef = useRef(false)

  // Keep a ref copy of tasks so the poll callback always sees the latest value
  // without needing `tasks` in its dependency array (which would reset the interval).
  const tasksRef = useRef<Task[]>(tasks)
  // eslint-disable-next-line react-hooks/refs -- intentional ref-sync pattern: mirrors state into ref so stable callbacks always see latest tasks without re-registering intervals
  tasksRef.current = tasks

  // -----------------------------------------------------------------------
  // Toast helper
  // -----------------------------------------------------------------------

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg)
    setToastVisible(true)
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    toastTimerRef.current = setTimeout(() => setToastVisible(false), 1500)
  }, [])

  // -----------------------------------------------------------------------
  // Save to server (debounced via markChanged)
  // -----------------------------------------------------------------------

  const saveToServer = useCallback(
    async (tasksToSave: Task[]) => {
      try {
        await fetch(`${getApiBase()}/focus/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tasks: tasksToSave }),
        })
        localStorage.setItem('lumbergh:focus:tasks_cache', JSON.stringify(tasksToSave))
        hasPendingSaveRef.current = false
        showToast('Saved')
      } catch {
        localStorage.setItem('lumbergh:focus:tasks_cache', JSON.stringify(tasksToSave))
        showToast('Cached locally')
      }
    },
    [showToast]
  )

  // -----------------------------------------------------------------------
  // markChanged — triggers a debounced save
  // -----------------------------------------------------------------------

  const markChanged = useCallback(() => {
    hasPendingSaveRef.current = true
    lastChangeTimeRef.current = Date.now()
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(() => {
      saveToServer(tasksRef.current)
    }, 500)
  }, [saveToServer])

  // -----------------------------------------------------------------------
  // CRUD helpers — each mutates state then calls markChanged
  // -----------------------------------------------------------------------

  const addTask = useCallback(
    (task: Task) => {
      setTasks((prev) => {
        const next = [...prev, task]
        return next
      })
      // markChanged is scheduled after the state update flushes
      // We use a microtask to ensure tasksRef is updated
      queueMicrotask(() => markChanged())
    },
    [markChanged]
  )

  const updateTask = useCallback(
    (id: string, updates: Partial<Task>) => {
      setTasks((prev) => prev.map((t) => (t.id === id ? ({ ...t, ...updates } as Task) : t)))
      queueMicrotask(() => markChanged())
    },
    [markChanged]
  )

  const deleteTask = useCallback(
    (id: string) => {
      setTasks((prev) => prev.filter((t) => t.id !== id))
      queueMicrotask(() => markChanged())
    },
    [markChanged]
  )

  const moveTaskToStatus = useCallback(
    (taskId: string, newStatus: string, beforeTaskId?: string | null) => {
      setTasks((prev) => {
        const idx = prev.findIndex((t) => t.id === taskId)
        if (idx === -1) return prev

        const task = { ...prev[idx]! }
        task.status = newStatus

        // Mark completed / clear completed based on status
        if (newStatus === 'done') {
          task.completed = true
          task.completed_date = todayISO()
        } else {
          task.completed = false
          task.completed_date = ''
        }

        // Remove the task from its current position
        const without = prev.filter((t) => t.id !== taskId)

        if (beforeTaskId) {
          // Insert before the specified task
          const beforeIdx = without.findIndex((t) => t.id === beforeTaskId)
          if (beforeIdx !== -1) {
            without.splice(beforeIdx, 0, task as Task)
            return without
          }
        }

        // beforeTaskId is null/undefined or not found — append at end of
        // the same-status group (preserves visual ordering)
        let insertIdx = -1
        for (let i = without.length - 1; i >= 0; i--) {
          if (without[i]!.status === newStatus) {
            insertIdx = i + 1
            break
          }
        }
        if (insertIdx === -1) {
          // No existing tasks with this status — just push
          without.push(task as Task)
        } else {
          without.splice(insertIdx, 0, task as Task)
        }
        return without
      })
      queueMicrotask(() => markChanged())
    },
    [markChanged]
  )

  const reorderTasks = useCallback(
    (reorderedTasks: Task[]) => {
      setTasks(reorderedTasks)
      queueMicrotask(() => markChanged())
    },
    [markChanged]
  )

  // -----------------------------------------------------------------------
  // Initial load
  // -----------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const res = await fetch(`${getApiBase()}/focus/tasks`)
        const json = await res.json()
        if (!cancelled) {
          const loaded: Task[] = json.tasks || []
          setTasks(loaded)
          localStorage.setItem('lumbergh:focus:tasks_cache', JSON.stringify(loaded))
        }
      } catch {
        const cached = localStorage.getItem('lumbergh:focus:tasks_cache')
        if (cached && !cancelled) {
          setTasks(JSON.parse(cached))
          showToast('Loaded from cache (server unavailable)')
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [showToast])

  // -----------------------------------------------------------------------
  // Polling (every 3 s)
  // -----------------------------------------------------------------------

  useEffect(() => {
    pollIntervalRef.current = setInterval(async () => {
      if (hasPendingSaveRef.current) return
      if (modalOpenRef.current) return

      const pollStart = Date.now()
      try {
        const res = await fetch(`${getApiBase()}/focus/tasks`)
        const json = await res.json()

        // Discard if a local change happened while we were fetching
        if (lastChangeTimeRef.current >= pollStart || hasPendingSaveRef.current) return

        const serverTasks: Task[] = json.tasks || []
        const serverStr = JSON.stringify(serverTasks)
        const localStr = JSON.stringify(tasksRef.current)

        if (serverStr !== localStr) {
          setTasks(serverTasks)
          localStorage.setItem('lumbergh:focus:tasks_cache', JSON.stringify(serverTasks))
        }
      } catch {
        /* ignore poll errors */
      }
    }, 3000)

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
    }
  }, [])

  // -----------------------------------------------------------------------
  // Cleanup save timeout on unmount
  // -----------------------------------------------------------------------

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    }
  }, [])

  // -----------------------------------------------------------------------
  // Context value (stable references via useCallback above)
  // -----------------------------------------------------------------------

  const value: TaskContextValue = {
    tasks,
    setTasks,
    addTask,
    updateTask,
    deleteTask,
    moveTaskToStatus,
    reorderTasks,
    markChanged,
    modalOpenRef,
    showToast,
    toastMessage,
    toastVisible,
  }

  return <TaskContext.Provider value={value}>{children}</TaskContext.Provider>
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

// eslint-disable-next-line react-refresh/only-export-components -- context hook intentionally exported from the same file as its provider; standard React context pattern
export function useTasks(): TaskContextValue {
  const ctx = useContext(TaskContext)
  if (!ctx) throw new Error('useTasks must be used inside <TaskProvider>')
  return ctx
}
