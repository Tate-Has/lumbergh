import { describe, it, expect } from 'vitest'
import { commitHeaderInfo, reviewFilePrompt } from './utils'
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

const compared: CommitDiff = {
  ...fetched,
  range: {
    from: {
      hash: '469af81721e5c0d2d9b0f8e5a2c1b3d4e5f60718',
      shortHash: '469af81',
      message: 'chore: bump deps',
      author: 'Jim Vogel',
      relativeDate: '3 days ago',
    },
    to: {
      hash: fetched.hash,
      shortHash: fetched.shortHash,
      message: fetched.message,
      author: fetched.author,
      relativeDate: fetched.relativeDate,
    },
    commitCount: 3,
  },
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

  it('describes a comparison of two commits as a range', () => {
    const info = commitHeaderInfo(compared, '469af81721e5', '27bb825a4c55')

    expect(info?.shortHash).toBe('469af81..27bb825')
    expect(info?.message).toBe('3 commits')
    expect(info?.compare?.from.hash).toBe(compared.range?.from.hash)
  })

  it('reads the same range whichever commit was shift-clicked', () => {
    const clickedNewerFirst = commitHeaderInfo(compared, '27bb825a4c55', '469af81721e5')

    expect(clickedNewerFirst?.shortHash).toBe('469af81..27bb825')
  })

  it('counts a single-commit span in the singular', () => {
    const one = { ...compared, range: { ...compared.range!, commitCount: 1 } }

    expect(commitHeaderInfo(one, '469af81721e5', '27bb825a4c55')?.message).toBe('1 commit')
  })

  it('waits for the range payload before claiming a comparison', () => {
    expect(commitHeaderInfo(fetched, '469af81721e5', '27bb825a4c55')).toBeNull()
    expect(commitHeaderInfo(compared, '469af81721e5', 'ffffffffffff')).toBeNull()
  })
})

describe('reviewFilePrompt', () => {
  it('asks for a review by path, ready to edit before sending', () => {
    expect(reviewFilePrompt('src/components/diff/FileDiff.tsx')).toBe(
      'Review src/components/diff/FileDiff.tsx'
    )
  })
})
