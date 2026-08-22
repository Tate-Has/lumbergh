import { describe, it, expect } from 'vitest'
import { prsByBranch, refBranchName, type PullRequest } from './pullRequests'

const pr = (number: number, headRefName: string): PullRequest => ({
  number,
  headRefName,
  title: `pr ${number}`,
  state: 'OPEN',
  url: `https://github.com/o/r/pull/${number}`,
  isDraft: false,
})

describe('refBranchName', () => {
  it('reads a remote ref as the branch it tracks', () => {
    expect(refBranchName('origin/fix/graph-hash')).toBe('fix/graph-hash')
    expect(refBranchName('fix/graph-hash')).toBe('fix/graph-hash')
  })

  it('leaves another remote alone rather than guessing', () => {
    expect(refBranchName('windows-fork/main')).toBe('windows-fork/main')
  })
})

describe('prsByBranch', () => {
  it('finds the PR for a branch under either of its names', () => {
    const byBranch = prsByBranch([pr(412, 'fix/graph-hash')])

    expect(byBranch.get(refBranchName('fix/graph-hash'))?.number).toBe(412)
    expect(byBranch.get(refBranchName('origin/fix/graph-hash'))?.number).toBe(412)
    expect(byBranch.get('main')).toBeUndefined()
  })

  it('survives an empty list, which is what a non-GitHub repo gives', () => {
    expect(prsByBranch([]).size).toBe(0)
  })

  it('keeps the lowest-numbered PR when a branch somehow has two', () => {
    const byBranch = prsByBranch([pr(500, 'shared'), pr(412, 'shared')])

    expect(byBranch.get('shared')?.number).toBe(412)
  })
})
