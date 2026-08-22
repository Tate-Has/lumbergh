/** The reset entries shared by the commit menu and the branch menu.
 *
 * Two menus offering resets that disagreed on wording, order and even meaning —
 * the branch menu's lone "Reset local to here" was silently a soft reset — is
 * what made the git view confusing. Both now render from here.
 */
export type ResetMode = 'soft' | 'hard'

export interface ResetMenuEntry {
  key: string
  label: string
  danger: boolean
  onClick: () => void
}

/** Hard is listed first on purpose: it is the reset this workflow reaches for. */
export function resetMenuEntries(onHard: () => void, onSoft: () => void): ResetMenuEntry[] {
  return [
    { key: 'reset-hard', label: 'Reset hard to here', danger: true, onClick: onHard },
    { key: 'reset-soft', label: 'Reset soft to here', danger: false, onClick: onSoft },
  ]
}

export function confirmHardReset(target: string): boolean {
  return confirm(
    `Reset HARD to ${target}?\n\nThis will DESTROY all uncommitted changes (staged, unstaged, and untracked files). This cannot be undone.`
  )
}
