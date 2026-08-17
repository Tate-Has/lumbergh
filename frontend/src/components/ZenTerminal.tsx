import { useCallback, useEffect, useRef, useState } from 'react'

const HIDE_AFTER_MS = 2000

interface ZenTerminalProps {
  children: React.ReactNode
  onExit: () => void
  active: boolean
}

// Always mounted around the terminal (see SessionDetail) so toggling zen never
// changes the terminal's position in the tree — that would remount it and tear
// down the WebSocket. The wrapper div always renders identically regardless of
// `active`; only the exit button and mouse-move timer are gated on it, so React
// never sees the child at this position change type across a toggle.
export default function ZenTerminal({ children, onExit, active }: ZenTerminalProps) {
  const [showExit, setShowExit] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const revealExit = useCallback(() => {
    setShowExit(true)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setShowExit(false), HIDE_AFTER_MS)
  }, [])

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    },
    []
  )

  return (
    <div className="h-full relative" onMouseMove={active ? revealExit : undefined}>
      {children}
      {active && (
        <button
          onClick={onExit}
          data-testid="zen-exit"
          className={`absolute top-2 right-2 z-30 px-2 py-1 rounded bg-bg-surface/80 border border-border-default text-text-tertiary hover:text-text-primary text-xs transition-opacity backdrop-blur-sm ${
            showExit ? 'opacity-100' : 'opacity-0 pointer-events-none'
          }`}
          title="Exit zen mode (Alt+Z)"
        >
          Exit zen
        </button>
      )}
    </div>
  )
}
