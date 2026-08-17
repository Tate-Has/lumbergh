/** Chords that drive the app rather than reaching the shell: Ctrl+[ / Ctrl+],
 * Alt+Left / Alt+Right, and Alt+Z. xterm must decline them so they bubble to the
 * window listeners in SessionDetail, useSessionSwitchKeys and useZenMode — and so
 * they never reach tmux as escape sequences. */
export function isSessionCycleChord(event: KeyboardEvent): boolean {
  if (event.ctrlKey && (event.key === '[' || event.key === ']')) return true
  if (event.altKey && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) return true
  // Physical key position, not event.key: on macOS Option+Z reports event.key === 'Ω',
  // which would make this chord dead. Trade-off: on Dvorak/AZERTY the key labelled
  // Z isn't the one that toggles.
  return event.altKey && !event.ctrlKey && !event.metaKey && event.code === 'KeyZ'
}
