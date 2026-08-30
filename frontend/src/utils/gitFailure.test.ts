import { describe, it, expect } from 'vitest'
import { describeGitFailure } from './gitFailure'

describe('describing a failed git action', () => {
  it('leads with the branch and keeps the worktree path as the detail', () => {
    const { message, detail } = describeGitFailure(
      {
        error: "'feature' is already used by worktree at '/src/aio-worktrees/feature'",
        branch: 'feature',
        worktree_path: '/src/aio-worktrees/feature',
      },
      409
    )

    expect(message).toContain('feature')
    expect(message).toContain('another worktree')
    expect(detail).toBe('/src/aio-worktrees/feature')
  })

  it('never shows the caller a command line', () => {
    const { message } = describeGitFailure(
      { error: 'x', branch: 'feature', worktree_path: '/wt' },
      409
    )

    expect(message).not.toContain('cmdline')
    expect(message).not.toContain('exit code')
  })

  it('passes an ordinary string detail straight through', () => {
    expect(describeGitFailure('Working directory has pending changes.', 409).message).toBe(
      'Working directory has pending changes.'
    )
  })

  it('falls back to the status when the body says nothing useful', () => {
    expect(describeGitFailure(undefined, 500).message).toBe('Failed (HTTP 500)')
    expect(describeGitFailure('   ', 500).message).toBe('Failed (HTTP 500)')
    expect(describeGitFailure({}, 400).message).toBe('Failed (HTTP 400)')
  })
})
