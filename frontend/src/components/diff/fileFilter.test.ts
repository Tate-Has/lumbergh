import { describe, it, expect } from 'vitest'
import { filterFiles } from './fileFilter'

const paths = [
  'backend/lumbergh/git_utils.py',
  'frontend/src/components/diff/FileDiff.tsx',
  'frontend/src/components/diff/FileList.tsx',
  'docs/release-workflow.md',
]

describe('filterFiles', () => {
  it('returns everything for an empty query', () => {
    expect(filterFiles(paths, '')).toEqual(paths)
    expect(filterFiles(paths, '   ')).toEqual(paths)
  })

  it('matches anywhere in the path, ignoring case', () => {
    expect(filterFiles(paths, 'GIT_UTILS')).toEqual(['backend/lumbergh/git_utils.py'])
    expect(filterFiles(paths, 'diff/')).toHaveLength(2)
  })

  it('puts filename matches above directory matches', () => {
    const hits = filterFiles(['diff/one.ts', 'other/diff.ts'], 'diff')

    expect(hits[0]).toBe('other/diff.ts')
  })

  it('says nothing rather than everything when nothing matches', () => {
    expect(filterFiles(paths, 'zzz')).toEqual([])
  })
})
