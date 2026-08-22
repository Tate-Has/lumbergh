/** Which pane, if any, fills the viewport.
 *
 * Alt+Z always targets 'main', so the chord can never strand the user in panel
 * focus — the panel is only reachable through its own maximize button. */
export type FocusTarget = 'none' | 'main' | 'panel'

const VALID: FocusTarget[] = ['none', 'main', 'panel']

/** `zenRaw` is the pre-focus `lumbergh:zenMode` value. Anyone already in zen
 * keeps their setting rather than silently losing it on upgrade. */
export function readStoredFocus(focusRaw: string | null, zenRaw: string | null): FocusTarget {
  if (focusRaw && (VALID as string[]).includes(focusRaw)) return focusRaw as FocusTarget
  if (focusRaw === null && zenRaw === 'true') return 'main'
  return 'none'
}

export function nextMainFocus(current: FocusTarget): FocusTarget {
  return current === 'main' ? 'none' : 'main'
}

export function nextPanelFocus(current: FocusTarget): FocusTarget {
  return current === 'panel' ? 'none' : 'panel'
}

/** Which pane the maximized view is showing. */
export type FullPane = 'panel' | 'terminal'

export interface PaneLayout {
  /** One pane fills the viewport, with the tab strip above it. */
  maximized: boolean
  /** That one pane is the terminal. */
  terminalMaximized: boolean
  /** The terminal is on screen, whether it shares the width or owns it. */
  terminalVisible: boolean
  /** Which side ResizablePanes gives up its width to. */
  collapse: 'left' | 'right' | null
}

/** `isTerminalOnly` means every panel is hidden, so there is nothing to
 * maximize and the terminal already owns the viewport. */
export function paneLayout(
  focus: FocusTarget,
  fullPane: FullPane,
  isTerminalOnly: boolean
): PaneLayout {
  const maximized = focus === 'panel' && !isTerminalOnly
  const terminalMaximized = maximized && fullPane === 'terminal'
  const terminalOwnsViewport = focus === 'main' || isTerminalOnly || terminalMaximized
  return {
    maximized,
    terminalMaximized,
    terminalVisible: !maximized || terminalMaximized,
    collapse: terminalOwnsViewport ? 'right' : maximized ? 'left' : null,
  }
}
