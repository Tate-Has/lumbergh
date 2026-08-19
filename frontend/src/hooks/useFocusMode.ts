import { useCallback, useEffect, useState } from 'react'
import { useIsDesktop } from './useMediaQuery'
import {
  type FocusTarget,
  nextMainFocus,
  nextPanelFocus,
  readStoredFocus,
} from '../utils/focusMode'

const STORAGE_KEY = 'lumbergh:focusMode'
const LEGACY_ZEN_KEY = 'lumbergh:zenMode'

/** Focus mode: one pane fills the desktop viewport, with the other pane and the
 * page banners not rendered. Alt+Z toggles the main pane in both directions —
 * Esc is deliberately not an exit key, because the terminal needs it.
 *
 * State lives in localStorage rather than server settings: it is a per-browser
 * view preference, like the ResizablePanes widths, and toggling must be
 * instant. */
export function useFocusMode() {
  const isDesktop = useIsDesktop()
  const [focus, setFocusState] = useState<FocusTarget>(() =>
    readStoredFocus(localStorage.getItem(STORAGE_KEY), localStorage.getItem(LEGACY_ZEN_KEY))
  )

  const setFocus = useCallback((next: FocusTarget) => {
    setFocusState(next)
    localStorage.setItem(STORAGE_KEY, next)
  }, [])

  const toggleMain = useCallback(() => setFocus(nextMainFocus(focus)), [focus, setFocus])
  const togglePanel = useCallback(() => setFocus(nextPanelFocus(focus)), [focus, setFocus])

  useEffect(() => {
    if (!isDesktop) return

    const onKeyDown = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      // Physical key position, not e.key: on macOS Option+Z reports e.key === 'Ω',
      // which would make this chord dead. Trade-off: on Dvorak/AZERTY the key
      // labelled Z isn't the one that toggles.
      if (e.code !== 'KeyZ') return
      e.preventDefault()
      setFocus(nextMainFocus(focus))
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isDesktop, focus, setFocus])

  // The stored preference survives a narrow viewport; only the rendered value is
  // gated, so widening the window restores what the user had.
  return { focus: isDesktop ? focus : ('none' as FocusTarget), setFocus, toggleMain, togglePanel }
}
