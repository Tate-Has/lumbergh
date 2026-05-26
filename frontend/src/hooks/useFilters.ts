import { useState, useCallback, useMemo } from 'react'
import type { Task, PriorityFilters } from '../types/focus'

interface UseFilters {
  priorityFilters: PriorityFilters
  projectFilters: Set<string>
  togglePriority: (key: 'high' | 'med' | 'low') => void
  toggleProject: (project: string) => void
  clearProjectFilters: () => void
  taskMatchesFilters: (task: Task) => boolean
  getUniqueProjects: (tasks: Task[]) => string[]
}

export function useFilters(): UseFilters {
  const [priorityFilters, setPriorityFilters] = useState<PriorityFilters>({
    high: true,
    med: true,
    low: false,
  })
  const [projectFilters, setProjectFilters] = useState<Set<string>>(new Set())

  const togglePriority = useCallback((key: 'high' | 'med' | 'low') => {
    setPriorityFilters((prev) => ({ ...prev, [key]: !prev[key] }))
  }, [])

  const toggleProject = useCallback((project: string) => {
    setProjectFilters((prev) => {
      const next = new Set(prev)
      if (next.has(project)) {
        next.delete(project)
      } else {
        next.add(project)
      }
      return next
    })
  }, [])

  const clearProjectFilters = useCallback(() => {
    setProjectFilters(new Set())
  }, [])

  const taskMatchesFilters = useCallback(
    (task: Task): boolean => {
      if (!priorityFilters[task.priority]) return false
      if (projectFilters.size > 0) {
        if (!task.project && !projectFilters.has('__none__')) return false
        if (task.project && !projectFilters.has(task.project)) return false
      }
      return true
    },
    [priorityFilters, projectFilters]
  )

  const getUniqueProjects = useCallback((tasks: Task[]): string[] => {
    const projects = new Set<string>()
    for (const t of tasks) {
      if (t.project) projects.add(t.project)
    }
    return [...projects].sort()
  }, [])

  return useMemo(
    () => ({
      priorityFilters,
      projectFilters,
      togglePriority,
      toggleProject,
      clearProjectFilters,
      taskMatchesFilters,
      getUniqueProjects,
    }),
    [
      priorityFilters,
      projectFilters,
      togglePriority,
      toggleProject,
      clearProjectFilters,
      taskMatchesFilters,
      getUniqueProjects,
    ]
  )
}
