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
