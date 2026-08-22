/** Which repo a new session started from this one should branch off.
 *
 * A worktree session's own workdir is a worktree, and git refuses to branch a
 * worktree from a worktree — the new one belongs to the repo this session came
 * from.
 */
export function spawnParentRepo(
  session: { workdir?: string | null; worktreeParentRepo?: string | null } | null
): string {
  if (!session) return ''
  return session.worktreeParentRepo || session.workdir || ''
}
