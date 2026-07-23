import type { Task } from '../types/focus'

export interface Repo {
  id: string
  name: string
  color: string
}

const REPO_COLOR_PALETTE = ['var(--color-action)', 'var(--color-purple)', 'var(--color-teal)']

export function deriveRepos(tasks: Task[]): Repo[] {
  const projects = new Set<string>()
  for (const t of tasks) {
    if (t.project) projects.add(t.project)
  }
  const sorted = [...projects].sort()

  return sorted.map((project, index) => ({
    id: project,
    name: project,
    color: REPO_COLOR_PALETTE[index % REPO_COLOR_PALETTE.length],
  }))
}
