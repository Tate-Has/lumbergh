/** Chords that drive the app rather than reaching the shell: Ctrl+[ / Ctrl+],
 * Alt+Left / Alt+Right, Alt+Z, and Alt+V. xterm must decline them so they bubble to
 * the window listeners in SessionDetail, useSessionSwitchKeys, useFocusMode and
 * useSessionView — and so they never reach tmux as escape sequences. */
export function isSessionCycleChord(event: KeyboardEvent): boolean {
  if (event.ctrlKey && (event.key === '[' || event.key === ']')) return true
  if (event.altKey && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) return true
  // Physical key position, not event.key: on macOS Option+Z/V reports event.key as
  // 'Ω'/'√', which would make these chords dead. Trade-off: on Dvorak/AZERTY the
  // key labelled Z or V isn't the one that toggles.
  const altOnly = event.altKey && !event.ctrlKey && !event.metaKey
  return altOnly && (event.code === 'KeyZ' || event.code === 'KeyV')
}

/** Keys that should first take the pane out of tmux copy-mode, because copy-mode
 * would otherwise spend them on itself instead of passing them to the agent.
 *
 * Escape is the one that matters: with `mode-keys vi` tmux binds it to
 * clear-selection, so pressing it to stop a runaway agent only drops the
 * copy-mode selection and stays in the mode — the agent never sees it. */
export function exitsScrollMode(event: KeyboardEvent): boolean {
  if (event.type !== 'keydown') return false
  if (event.ctrlKey || event.metaKey || event.altKey) return false
  return event.key.length === 1 || event.key === 'Escape'
}
