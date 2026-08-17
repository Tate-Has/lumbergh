import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'lumbergh:sessionView'

export type SessionView = 'term' | 'conv'

/** Which rendering of the session the main pane shows: the raw terminal, or the
 * conversation feed. Both stay mounted; this only picks which one is visible.
 *
 * Stored per browser rather than per session — it is a viewing preference, not a
 * property of any one session. */
export function useSessionView() {
  const [view, setViewState] = useState<SessionView>(() =>
    localStorage.getItem(STORAGE_KEY) === 'conv' ? 'conv' : 'term'
  )

  const setView = useCallback((next: SessionView) => {
    setViewState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }, [])

  const toggleView = useCallback(() => setView(view === 'term' ? 'conv' : 'term'), [view, setView])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      if (e.code !== 'KeyV') return
      e.preventDefault()
      setView(view === 'term' ? 'conv' : 'term')
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [view, setView])

  return { view, setView, toggleView }
}
