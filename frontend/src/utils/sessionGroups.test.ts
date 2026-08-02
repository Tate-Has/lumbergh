import { describe, it, expect } from 'vitest'
import { groupSessions } from './sessionGroups'
import type { SessionBase } from './sessionStatus'

interface Row extends SessionBase {
  lastUsedAt?: string | null
}

function row(name: string, over: Partial<Row> = {}): Row {
  return {
    name,
    alive: true,
    displayName: null,
    idleState: 'idle',
    role: 'session',
    parent: null,
    ...over,
  }
}

describe('groupSessions', () => {
  it('nests a worker under its live parent', () => {
    const sessions = [row('lumbergh'), row('port-644', { role: 'worker', parent: 'lumbergh' })]
    const { items } = groupSessions(sessions)
    expect(items).toHaveLength(1)
    expect(items[0].parent.name).toBe('lumbergh')
    expect(items[0].workers.map((w) => w.name)).toEqual(['port-644'])
  })

  it('extracts Bill and keeps him out of items', () => {
    const sessions = [row('bill', { role: 'bill' }), row('lumbergh')]
    const { bill, items } = groupSessions(sessions)
    expect(bill?.name).toBe('bill')
    expect(items.map((i) => i.parent.name)).toEqual(['lumbergh'])
  })

  it('surfaces an orphan worker as a top-level solo', () => {
    const sessions = [row('auth-fix', { role: 'worker', parent: 'herdr' })]
    const { items } = groupSessions(sessions)
    expect(items).toHaveLength(1)
    expect(items[0].parent.name).toBe('auth-fix')
    expect(items[0].workers).toEqual([])
  })

  it('a plain session with no workers is a solo (empty workers)', () => {
    const { items } = groupSessions([row('quotr')])
    expect(items[0].workers).toEqual([])
  })

  it('orders top-level items by urgency then recency', () => {
    const sessions = [
      row('calm', { idleState: 'working', lastUsedAt: '2026-01-01' }),
      row('urgent', { idleState: 'blocked', lastUsedAt: '2025-01-01' }),
      row('recent', { idleState: 'working', lastUsedAt: '2026-06-01' }),
    ]
    const { items } = groupSessions(sessions)
    expect(items.map((i) => i.parent.name)).toEqual(['urgent', 'recent', 'calm'])
  })
})
