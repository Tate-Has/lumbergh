import { describe, it, expect } from 'vitest'
import { applyGraphResponse, type GraphResponse } from './graphSync'
import type { GraphCommit, GraphData } from '../diff/types'

function commit(hash: string): GraphCommit {
  return {
    hash,
    shortHash: '',
    message: `commit ${hash}`,
    author: 'someone',
    relativeDate: '2026-01-01T00:00:00Z',
    parents: [],
    refs: [],
  }
}

function graph(hashes: string[], version = 'v1'): GraphData {
  return {
    commits: hashes.map(commit),
    branches: [],
    head: { hash: hashes[0] ?? '', branch: 'main' },
    workingChanges: null,
    worktrees: [],
    version,
  }
}

const SMALL_FIELDS = {
  branches: [],
  head: { hash: 'aaaaaaaaaaaa', branch: 'main' },
  workingChanges: null,
  worktrees: [],
}

describe('applyGraphResponse', () => {
  it('keeps the current graph when nothing changed', () => {
    const previous = graph(['aaaaaaaaaaaa', 'bbbbbbbbbbbb'])

    const { graph: next, cursorValid } = applyGraphResponse(previous, {
      unchanged: true,
      version: 'v1',
    })

    expect(next).toBe(previous)
    expect(cursorValid).toBe(true)
  })

  it('replaces everything on a keyframe', () => {
    const previous = graph(['old1old1old1'])

    const { graph: next } = applyGraphResponse(previous, graph(['newnewnewnew'], 'v2'))

    expect(next!.commits.map((c) => c.hash)).toEqual(['newnewnewnew'])
  })

  it('derives shortHash on keyframe commits', () => {
    const { graph: next } = applyGraphResponse(null, graph(['abcdef123456']))

    expect(next!.commits[0].shortHash).toBe('abcdef1')
  })

  it('merges added commits into the order the server describes', () => {
    const previous = graph(['bbbbbbbbbbbb', 'cccccccccccc'])

    const { graph: next, cursorValid } = applyGraphResponse(previous, {
      delta: true,
      version: 'v2',
      added: [commit('aaaaaaaaaaaa')],
      order: ['aaaaaaaaaaaa', 'bbbbbbbbbbbb', 'cccccccccccc'],
      ...SMALL_FIELDS,
    } as GraphResponse)

    expect(cursorValid).toBe(true)
    expect(next!.commits.map((c) => c.hash)).toEqual([
      'aaaaaaaaaaaa',
      'bbbbbbbbbbbb',
      'cccccccccccc',
    ])
    expect(next!.commits[0].shortHash).toBe('aaaaaaa')
  })

  it('evicts commits the server left out of the order', () => {
    const previous = graph(['aaaaaaaaaaaa', 'bbbbbbbbbbbb', 'cccccccccccc'])

    const { graph: next } = applyGraphResponse(previous, {
      delta: true,
      version: 'v2',
      added: [],
      order: ['aaaaaaaaaaaa', 'bbbbbbbbbbbb'],
      ...SMALL_FIELDS,
    } as GraphResponse)

    expect(next!.commits.map((c) => c.hash)).toEqual(['aaaaaaaaaaaa', 'bbbbbbbbbbbb'])
  })

  it('invalidates the cursor when the order names a commit we never received', () => {
    const previous = graph(['bbbbbbbbbbbb'])

    const { graph: next, cursorValid } = applyGraphResponse(previous, {
      delta: true,
      version: 'v2',
      added: [],
      order: ['missingmissi', 'bbbbbbbbbbbb'],
      ...SMALL_FIELDS,
    } as GraphResponse)

    expect(cursorValid).toBe(false)
    expect(next).toBe(previous)
  })

  it('invalidates the cursor when a delta arrives with nothing to apply it to', () => {
    const { cursorValid } = applyGraphResponse(null, {
      delta: true,
      version: 'v2',
      added: [],
      order: ['aaaaaaaaaaaa'],
      ...SMALL_FIELDS,
    } as GraphResponse)

    expect(cursorValid).toBe(false)
  })

  it('applies the keep shorthand without an explicit order', () => {
    const previous = graph(['bbbbbbbbbbbb', 'cccccccccccc'])

    const { graph: next, cursorValid } = applyGraphResponse(previous, {
      delta: true,
      version: 'v2',
      added: [commit('aaaaaaaaaaaa')],
      keep: 2,
      ...SMALL_FIELDS,
    } as GraphResponse)

    expect(cursorValid).toBe(true)
    expect(next!.commits.map((c) => c.hash)).toEqual([
      'aaaaaaaaaaaa',
      'bbbbbbbbbbbb',
      'cccccccccccc',
    ])
    expect(next!.commits[0].shortHash).toBe('aaaaaaa')
  })

  it('drops the tail the keep shorthand excludes', () => {
    const previous = graph(['aaaaaaaaaaaa', 'bbbbbbbbbbbb', 'cccccccccccc'])

    const { graph: next } = applyGraphResponse(previous, {
      delta: true,
      version: 'v2',
      added: [],
      keep: 2,
      ...SMALL_FIELDS,
    } as GraphResponse)

    expect(next!.commits.map((c) => c.hash)).toEqual(['aaaaaaaaaaaa', 'bbbbbbbbbbbb'])
  })

  it('invalidates the cursor when keep exceeds what we hold', () => {
    const previous = graph(['aaaaaaaaaaaa'])

    const { cursorValid } = applyGraphResponse(previous, {
      delta: true,
      version: 'v2',
      added: [],
      keep: 99,
      ...SMALL_FIELDS,
    } as GraphResponse)

    expect(cursorValid).toBe(false)
  })

  it('carries the small fields through a delta', () => {
    const previous = graph(['bbbbbbbbbbbb'])

    const { graph: next } = applyGraphResponse(previous, {
      delta: true,
      version: 'v2',
      added: [],
      keep: 1,
      ...SMALL_FIELDS,
      workingChanges: { files: 3, staged: 1, unstaged: 2 },
    } as GraphResponse)

    expect(next!.workingChanges).toEqual({ files: 3, staged: 1, unstaged: 2 })
    expect(next!.version).toBe('v2')
  })
})
