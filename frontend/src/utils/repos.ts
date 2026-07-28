import type { Task } from '../types/focus'

export interface Repo {
  id: string
  name: string
  color: string
  /** Absolute filesystem path, when this repo matches one found under a configured search directory. */
  path?: string
}

/** Shape returned by GET /api/directories/search — the same source the create-session picker uses. */
export interface AvailableRepo {
  path: string
  name: string
}

const REPO_COLOR_PALETTE = ['var(--color-action)', 'var(--color-purple)', 'var(--color-teal)']

/**
 * Repo lanes are the union of every distinct task.project string (so existing/legacy
 * tasks never lose their lane) and every repo found via the configured search
 * directories (so a repo shows up before any task references it, and its `path` is
 * known up front for launching agents). Matched by name against `availableRepos`,
 * which is the same {name, path} shape the create-session directory picker uses.
 */
export function deriveRepos(tasks: Task[], availableRepos: AvailableRepo[] = []): Repo[] {
  const names = new Set<string>()
  for (const t of tasks) {
    if (t.project) names.add(t.project)
  }
  for (const r of availableRepos) {
    names.add(r.name)
  }
  const sorted = [...names].sort()
  const pathByName = new Map(availableRepos.map((r) => [r.name, r.path]))

  return sorted.map((name, index) => ({
    id: name,
    name,
    color: REPO_COLOR_PALETTE[index % REPO_COLOR_PALETTE.length],
    path: pathByName.get(name),
  }))
}
