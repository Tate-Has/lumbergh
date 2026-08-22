import { describe, it, expect } from 'vitest'
import { parseDiffPayload } from './diffPayload'

describe('parseDiffPayload', () => {
  it('accepts a real diff', () => {
    const payload = { files: [{ path: 'a.ts', diff: '' }], stats: { additions: 1, deletions: 0 } }

    expect(parseDiffPayload(payload)?.files).toHaveLength(1)
  })

  it('rejects an error body, which is what a failing endpoint actually returns', () => {
    expect(parseDiffPayload({ detail: '/home/j/worktrees/1187' })).toBeNull()
  })

  it('rejects anything without a files array', () => {
    expect(parseDiffPayload(null)).toBeNull()
    expect(parseDiffPayload('nope')).toBeNull()
    expect(parseDiffPayload({ files: 'not-an-array' })).toBeNull()
  })

  it('fills in stats when the payload omits them', () => {
    expect(parseDiffPayload({ files: [] })?.stats).toEqual({ additions: 0, deletions: 0 })
  })
})
