/** What reap answers with when it refuses. `reason` is the blocker it named. */
export interface ReapRefusal {
  error?: string
  reason?: 'dirty' | 'unlanded' | 'unknown'
  commits?: number | null
}

/** Say what forcing past a refusal actually destroys.
 *
 * The counts come from the refusal, not from the listing, so this never invents a
 * number: `dirty` has no count to give and says so in words. */
export function describeLoss(refusal: ReapRefusal): string {
  if (refusal.reason === 'dirty') {
    return 'It has uncommitted changes, which exist nowhere else and will be lost.'
  }
  if (refusal.reason === 'unlanded') {
    const n = refusal.commits ?? 0
    const subject = n === 1 ? '1 commit here is' : `${n} commits here are`
    return `${subject} on no other branch and no remote, and will be lost.`
  }
  if (refusal.reason === 'unknown') {
    return 'Whether this work landed anywhere could not be established.'
  }
  return refusal.error || 'This worktree could not be removed.'
}
