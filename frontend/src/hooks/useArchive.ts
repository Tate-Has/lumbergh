import { useState, useCallback } from 'react'
import { todayISO } from '../utils/focus'
import type { Task } from '../types/focus'
import { getApiBase } from '../config'

export interface ArchiveTask {
  title: string
  project: string
  priority: string
  blocker: string
  check_in_note: string
  archived_date: string
}

export interface ArchiveNote {
  date: string
  content: string
}

export interface ArchiveData {
  tasks: ArchiveTask[]
  notes: ArchiveNote[]
}

interface UseArchive {
  archiveData: ArchiveData | null
  loading: boolean
  error: string | null
  openArchive: () => Promise<void>
  archiveDoneTasks: (
    tasks: Task[],
    onTasksChanged: (newTasks: Task[]) => void
  ) => Promise<string | null>
}

export function useArchive(): UseArchive {
  const [archiveData, setArchiveData] = useState<ArchiveData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const openArchive = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${getApiBase()}/focus/archive`)
      const data: ArchiveData = await res.json()
      setArchiveData(data)
    } catch {
      setError('Could not load archive.')
      setArchiveData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const archiveDoneTasks = useCallback(
    async (tasks: Task[], onTasksChanged: (newTasks: Task[]) => void): Promise<string | null> => {
      const doneTasks = tasks.filter((t) => t.status === 'done')
      if (!doneTasks.length) return null

      const today = todayISO()

      let currentArchive: ArchiveData = { tasks: [], notes: [] }
      try {
        const res = await fetch(`${getApiBase()}/focus/archive`)
        currentArchive = await res.json()
        if (!currentArchive.tasks) currentArchive.tasks = []
        if (!currentArchive.notes) currentArchive.notes = []
      } catch {
        /* start with empty archive */
      }

      const newArchiveTasks: ArchiveTask[] = doneTasks.map((t) => ({
        title: t.title,
        project: t.project || '',
        priority: t.priority || 'med',
        blocker: t.blocker || '',
        check_in_note: t.check_in_note || '',
        archived_date: t.completed_date || today,
      }))
      newArchiveTasks.sort((a, b) => b.archived_date.localeCompare(a.archived_date))

      currentArchive.tasks = [...newArchiveTasks, ...currentArchive.tasks]

      try {
        await fetch(`${getApiBase()}/focus/archive`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentArchive),
        })
      } catch {
        return 'Failed to write archive'
      }

      onTasksChanged(tasks.filter((t) => t.status !== 'done'))

      const count = doneTasks.length
      return `Archived ${count} task${count > 1 ? 's' : ''}`
    },
    []
  )

  return { archiveData, loading, error, openArchive, archiveDoneTasks }
}
