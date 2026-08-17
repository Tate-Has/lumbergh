import { useCallback, useState } from 'react'

const STORAGE_KEY = 'lumbergh:conversationFontSize'
const MIN_SCALE = 0.6
const MAX_SCALE = 2

function readStored(): number {
  const saved = parseFloat(localStorage.getItem(STORAGE_KEY) ?? '')
  return !isNaN(saved) && saved >= MIN_SCALE && saved <= MAX_SCALE ? saved : 1
}

/** The Conv feed's zoom level, driven by the header's zoom control when `view`
 * is 'conv'. Stored per browser (like `useSessionView`) since it is a viewing
 * preference, not a property of any one session. */
export function useConversationScale() {
  const [scale, setScaleState] = useState<number>(readStored)

  const setScale = useCallback((next: number) => {
    const clamped = Math.min(MAX_SCALE, Math.max(MIN_SCALE, next))
    setScaleState(clamped)
    localStorage.setItem(STORAGE_KEY, String(clamped))
  }, [])

  return { scale, setScale }
}
