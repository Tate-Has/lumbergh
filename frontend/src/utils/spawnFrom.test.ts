import { describe, it, expect } from 'vitest'
import { spawnParentRepo } from './spawnFrom'

describe('spawnParentRepo', () => {
  it('branches a direct session from its own workdir', () => {
    expect(spawnParentRepo({ workdir: '/home/j/src/lumbergh' })).toBe('/home/j/src/lumbergh')
  })

  it('branches a worktree session from the repo it came from, not the worktree', () => {
    const repo = spawnParentRepo({
      workdir: '/home/j/.lumbergh/worktrees/issue-412',
      worktreeParentRepo: '/home/j/src/lumbergh',
    })

    expect(repo).toBe('/home/j/src/lumbergh')
  })

  it('has nothing to offer for an orphan session with no workdir', () => {
    expect(spawnParentRepo({ workdir: null })).toBe('')
    expect(spawnParentRepo(null)).toBe('')
  })
})
