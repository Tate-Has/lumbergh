import { useCallback, useEffect, useState } from 'react'
import { useIsDesktop } from './useMediaQuery'

const STORAGE_KEY = 'lumbergh:zenMode'

/** Zen mode: the terminal fills the desktop viewport, with the side panel and page
 * banners not rendered. Alt+Z toggles it in both directions — Esc is deliberately
 * not an exit key, because the terminal needs it.
 *
 * State lives in localStorage rather than server settings: it is a per-browser view
 * preference, like the ResizablePanes widths, and toggling must be instant. */
export function useZenMode() {
  const isDesktop = useIsDesktop()
  const [isZen, setIsZen] = useState(() => localStorage.getItem(STORAGE_KEY) === 'true')

  const setAndStore = useCallback((next: boolean) => {
    setIsZen(next)
    localStorage.setItem(STORAGE_KEY, String(next))
  }, [])

  const toggleZen = useCallback(() => setAndStore(!isZen), [isZen, setAndStore])
  const exitZen = useCallback(() => setAndStore(false), [setAndStore])

  useEffect(() => {
    if (!isDesktop) return

    const onKeyDown = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      if (e.key.toLowerCase() !== 'z') return
      e.preventDefault()
      setAndStore(!isZen)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isDesktop, isZen, setAndStore])

  return { isZen: isDesktop && isZen, toggleZen, exitZen }
}
