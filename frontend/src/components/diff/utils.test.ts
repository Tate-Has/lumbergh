import { describe, it, expect } from 'vitest'
import { commitHeaderInfo } from './utils'
import type { CommitDiff } from './types'

const fetched: CommitDiff = {
  hash: '27bb825a4c5514325bb0be25a93afa00d85276af',
  shortHash: '27bb825',
  message: 'fix(sessions): a container session reports its windows state',
  author: 'Jim Vogel',
  relativeDate: '2 hours ago',
  files: [],
  stats: { additions: 0, deletions: 0 },
}

describe('commitHeaderInfo', () => {
  it('matches the abbreviated hash the graph selects against the full one the API returns', () => {
    const info = commitHeaderInfo(fetched, '27bb825a4c55')

    expect(info).not.toBeNull()
    expect(info?.hash).toBe(fetched.hash)
    expect(info?.shortHash).toBe('27bb825')
    expect(info?.message).toBe(fetched.message)
  })

  it('still matches a full hash', () => {
    expect(commitHeaderInfo(fetched, fetched.hash)?.hash).toBe(fetched.hash)
  })

  it('has nothing to show with no commit selected', () => {
    expect(commitHeaderInfo(fetched, null)).toBeNull()
    expect(commitHeaderInfo(fetched, '')).toBeNull()
  })

  it('has nothing to show while the selected commit is still loading', () => {
    expect(commitHeaderInfo(null, '27bb825a4c55')).toBeNull()
    expect(commitHeaderInfo(fetched, '469af81721e5')).toBeNull()
  })
})
