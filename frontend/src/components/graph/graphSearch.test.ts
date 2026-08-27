import { describe, it, expect } from 'vitest'
import { parseQuery, findMatches, hashKey, anyRowVisible } from './graphSearch'
import type { GraphCommit } from '../diff/types'

function commit(overrides: Partial<GraphCommit> = {}): GraphCommit {
  return {
    hash: 'abc123def456',
    shortHash: 'abc123d',
    message: 'fix the thing',
    author: 'Jim Vogel',
    authorEmail: 'jim@example.com',
    relativeDate: '2026-01-01T00:00:00Z',
    parents: [],
    refs: [],
    ...overrides,
  }
}

describe('parseQuery', () => {
  it('treats bare words as free text', () => {
    expect(parseQuery('fix the thing')).toEqual({
      text: 'fix the thing',
      author: undefined,
      file: undefined,
      needsHistory: false,
    })
  })

  it('pulls out an author: qualifier and leaves the rest as text', () => {
    expect(parseQuery('author:jim rebase')).toEqual({
      text: 'rebase',
      author: 'jim',
      file: undefined,
      needsHistory: false,
    })
  })

  it('marks a file: qualifier as needing history, since the payload cannot answer it', () => {
    const q = parseQuery('file:src/main.py')
    expect(q.file).toBe('src/main.py')
    expect(q.needsHistory).toBe(true)
  })

  it('accepts a quoted qualifier value containing spaces', () => {
    expect(parseQuery('author:"Jim Vogel"').author).toBe('Jim Vogel')
  })

  it('reports an empty query as empty text with no qualifiers', () => {
    expect(parseQuery('   ')).toEqual({
      text: '',
      author: undefined,
      file: undefined,
      needsHistory: false,
    })
  })
})

describe('findMatches', () => {
  const commits = [
    commit({ hash: 'aaa111', shortHash: 'aaa111', message: 'fix the parser', author: 'Jim Vogel' }),
    commit({
      hash: 'bbb222',
      shortHash: 'bbb222',
      message: 'add a widget',
      author: 'Ada Lovelace',
      authorEmail: 'ada@example.com',
    }),
    commit({
      hash: 'ccc333',
      shortHash: 'ccc333',
      message: 'docs pass',
      author: 'Jim Vogel',
      refs: [{ name: 'feature/search', local: true, remote: false }],
    }),
  ]

  it('returns no matches for an empty query, so nothing is dimmed', () => {
    expect(findMatches(commits, parseQuery(''))).toEqual(new Set())
  })

  it('matches on message text, case-insensitively', () => {
    expect(findMatches(commits, parseQuery('PARSER'))).toEqual(new Set(['aaa111']))
  })

  it('matches on author name', () => {
    expect(findMatches(commits, parseQuery('lovelace'))).toEqual(new Set(['bbb222']))
  })

  it('matches on a short hash prefix', () => {
    expect(findMatches(commits, parseQuery('ccc3'))).toEqual(new Set(['ccc333']))
  })

  it('matches on a ref name, so branch names are findable', () => {
    expect(findMatches(commits, parseQuery('feature/search'))).toEqual(new Set(['ccc333']))
  })

  it('narrows by author: without matching that name in the message', () => {
    expect(findMatches(commits, parseQuery('author:jim'))).toEqual(new Set(['aaa111', 'ccc333']))
  })

  it('requires both the author and the text to match', () => {
    expect(findMatches(commits, parseQuery('author:jim docs'))).toEqual(new Set(['ccc333']))
  })

  it('matches nothing locally when the query needs history', () => {
    expect(findMatches(commits, parseQuery('file:src/main.py'))).toEqual(new Set())
  })
})

describe('hashKey', () => {
  it('reduces a full hash to the abbreviation the graph payload sends', () => {
    expect(hashKey('f724a9c12b23aa020f0431c0a57f00f6be756b08')).toBe('f724a9c12b23')
  })

  it('leaves an already-abbreviated hash alone, so both sides agree', () => {
    expect(hashKey('f724a9c12b23')).toBe('f724a9c12b23')
  })

  it('lets a full hash from history search be found among abbreviated graph hashes', () => {
    const loaded = new Set(['f7e98e9aa856', 'f724a9c12b23'].map(hashKey))
    expect(loaded.has(hashKey('f724a9c12b23aa020f0431c0a57f00f6be756b08'))).toBe(true)
  })
})

describe('anyRowVisible', () => {
  const viewport = { scrollTop: 100, clientHeight: 200 }
  const rowToY = (row: number) => row * 40

  it('sees a row sitting inside the viewport', () => {
    expect(anyRowVisible([4], rowToY, 40, viewport)).toBe(true)
  })

  it('does not see a row above the viewport', () => {
    expect(anyRowVisible([0], rowToY, 40, viewport)).toBe(false)
  })

  it('does not see a row below the viewport', () => {
    expect(anyRowVisible([20], rowToY, 40, viewport)).toBe(false)
  })

  it('counts a row only partly on screen as visible', () => {
    expect(anyRowVisible([2], rowToY, 40, viewport)).toBe(true)
  })

  it('is false when there are no rows at all', () => {
    expect(anyRowVisible([], rowToY, 40, viewport)).toBe(false)
  })

  it('is true when any one of several rows is on screen', () => {
    expect(anyRowVisible([0, 20, 4], rowToY, 40, viewport)).toBe(true)
  })
})
