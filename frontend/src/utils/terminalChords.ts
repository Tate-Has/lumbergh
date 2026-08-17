/** Chords that drive the app rather than reaching the shell: Ctrl+[ / Ctrl+],
 * Alt+Left / Alt+Right, Alt+Z, and Alt+V. xterm must decline them so they bubble to
 * the window listeners in SessionDetail, useSessionSwitchKeys, useZenMode and
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
