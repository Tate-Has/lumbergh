import { describe, it, expect } from 'vitest'
import { orderSessionsForNavigator, adjacentSessionName } from './sessionOrder'
import type { SessionBase } from './sessionStatus'

function session(name: string, overrides: Partial<SessionBase> = {}): SessionBase {
  return { name, alive: true, displayName: null, ...overrides }
}

describe('orderSessionsForNavigator', () => {
  it('puts bill first, then starred, then the rest, each name-sorted', () => {
    const ordered = orderSessionsForNavigator([
      session('docs'),
      session('web', { theOne: true }),
      session('bill'),
      session('db'),
      session('api', { theOne: true }),
    ])

    expect(ordered.map((s) => s.name)).toEqual(['bill', 'api', 'web', 'db', 'docs'])
  })

  it('excludes dead and paused sessions', () => {
    const ordered = orderSessionsForNavigator([
      session('api'),
      session('db', { alive: false }),
      session('docs', { paused: true }),
    ])

    expect(ordered.map((s) => s.name)).toEqual(['api'])
  })

  it('omits bill when there is no bill session', () => {
    const ordered = orderSessionsForNavigator([session('web'), session('api')])

    expect(ordered.map((s) => s.name)).toEqual(['api', 'web'])
  })
})

describe('adjacentSessionName', () => {
  const ordered = orderSessionsForNavigator([session('bill'), session('api'), session('db')])

  it('steps to the neighbour in each direction', () => {
    expect(adjacentSessionName(ordered, 'api', 'next')).toBe('db')
    expect(adjacentSessionName(ordered, 'api', 'prev')).toBe('bill')
  })

  it('wraps past the last entry', () => {
    expect(adjacentSessionName(ordered, 'db', 'next')).toBe('bill')
  })

  it('wraps before the first entry', () => {
    expect(adjacentSessionName(ordered, 'bill', 'prev')).toBe('db')
  })

  it('returns null when there is nowhere else to go', () => {
    const alone = orderSessionsForNavigator([session('api')])

    expect(adjacentSessionName(alone, 'api', 'next')).toBeNull()
    expect(adjacentSessionName(alone, 'api', 'prev')).toBeNull()
  })

  it('returns null when the current session is not in the list', () => {
    expect(adjacentSessionName(ordered, 'ghost', 'next')).toBeNull()
  })
})
