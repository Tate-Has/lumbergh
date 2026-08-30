/** The shape the checkout endpoint returns when a worktree holds the branch. */
interface WorktreeConflict {
  error: string
  branch?: string
  worktree_path?: string
}

function isWorktreeConflict(detail: unknown): detail is WorktreeConflict {
  return (
    typeof detail === 'object' &&
    detail !== null &&
    typeof (detail as WorktreeConflict).worktree_path === 'string'
  )
}

/** Turn a FastAPI error detail into something worth reading.
 *
 * A branch held by another worktree is the case worth special-casing: git's own
 * sentence is accurate but buries the path, and the path is the whole answer to
 * "why can't I check this out" — so it becomes the toast's second line. */
export function describeGitFailure(
  detail: unknown,
  status: number
): { message: string; detail?: string } {
  if (isWorktreeConflict(detail)) {
    const branch = detail.branch ? `‘${detail.branch}’` : 'That branch'
    return {
      message: `${branch} is already checked out in another worktree`,
      detail: detail.worktree_path,
    }
  }
  if (typeof detail === 'string' && detail.trim()) {
    return { message: detail }
  }
  return { message: `Failed (HTTP ${status})` }
}
