import { useState, useEffect } from 'react'
import { getApiBase } from '../config'
import type { AvailableRepo } from '../utils/repos'

/**
 * Repos found under the configured search directories — the same
 * GET /api/directories/search backing the create-session directory picker,
 * so the Workspace repo lists always match what launching a new agent offers.
 */
export function useAvailableRepos(): AvailableRepo[] {
  const [repos, setRepos] = useState<AvailableRepo[]>([])

  useEffect(() => {
    let cancelled = false
    fetch(`${getApiBase()}/directories/search?query=`)
      .then((res) => (res.ok ? res.json() : { directories: [] }))
      .then((data) => {
        if (!cancelled) setRepos(data.directories || [])
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  return repos
}
