import { describe, it, expect } from 'vitest'
import { orderSessionsForNavigator, adjacentSessionName, navigatorGroups } from './sessionOrder'
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

  it('trails each worker directly behind its parent', () => {
    const ordered = orderSessionsForNavigator([
      session('docs'),
      session('api-fix', { role: 'worker', parent: 'api' }),
      session('api'),
      session('api-docs', { role: 'worker', parent: 'api' }),
    ])

    expect(ordered.map((s) => s.name)).toEqual(['api', 'api-docs', 'api-fix', 'docs'])
  })

  it('keeps a worker beside a starred parent instead of demoting it', () => {
    const groups = navigatorGroups([
      session('api', { theOne: true }),
      session('api-fix', { role: 'worker', parent: 'api' }),
      session('docs'),
    ])

    expect(groups.starred.map((s) => s.name)).toEqual(['api', 'api-fix'])
    expect(groups.rest.map((s) => s.name)).toEqual(['docs'])
  })

  it('adopts a worker whose recorded parent died into the session on its repo', () => {
    const ordered = orderSessionsForNavigator([
      session('mom_work'),
      session('lumbergh', { workdir: '/src/lumbergh' }),
      session('badge-fix', {
        role: 'worker',
        parent: 'zen-verify-htop',
        worktreeParentRepo: '/src/lumbergh',
      }),
      session('aio'),
    ])

    expect(ordered.map((s) => s.name)).toEqual(['aio', 'lumbergh', 'badge-fix', 'mom_work'])
  })

  it('promotes an orphan worker to a top-level session', () => {
    const ordered = orderSessionsForNavigator([
      session('stray', { role: 'worker', parent: 'gone', worktreeParentRepo: '/src/vanished' }),
      session('api'),
    ])

    expect(ordered.map((s) => s.name)).toEqual(['api', 'stray'])
  })
})

describe('navigatorGroups', () => {
  it('splits bill, starred, and the rest', () => {
    const groups = navigatorGroups([
      session('bill'),
      session('web', { theOne: true }),
      session('db'),
    ])

    expect(groups.bill?.name).toBe('bill')
    expect(groups.starred.map((s) => s.name)).toEqual(['web'])
    expect(groups.rest.map((s) => s.name)).toEqual(['db'])
  })

  it('has no bill when none is running', () => {
    expect(navigatorGroups([session('api')]).bill).toBeNull()
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
