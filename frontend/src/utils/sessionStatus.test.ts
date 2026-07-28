import { describe, it, expect } from 'vitest'
import { getSessionStatus, statusColorClasses, sessionUrgencyRank } from './sessionStatus'

describe('getSessionStatus', () => {
  it('maps blocked to a violet, pulsing, "waiting on you" status', () => {
    const status = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'blocked',
      displayName: null,
    })
    expect(status.color).toBe('purple')
    expect(status.pulse).toBe(true)
    expect(status.label).toBe('Blocked — waiting on you')
  })

  it('exposes a color class for the purple accent', () => {
    expect(statusColorClasses.purple).toBeDefined()
    expect(statusColorClasses.purple.text).toContain('purple')
  })
})

describe('sessionUrgencyRank', () => {
  it('ranks the pinned favorite above everything', () => {
    expect(sessionUrgencyRank({ theOne: true, idleState: 'idle' })).toBe(0)
    expect(sessionUrgencyRank({ theOne: true, idleState: 'blocked' })).toBe(0)
  })

  it('ranks blocked above ordinary sessions', () => {
    expect(sessionUrgencyRank({ theOne: false, idleState: 'blocked' })).toBe(1)
    expect(sessionUrgencyRank({ theOne: false, idleState: 'working' })).toBe(3)
    expect(sessionUrgencyRank({ idleState: 'idle' })).toBe(3)
  })
})

describe('unseen "while you were away" overlay', () => {
  it('labels an unseen idle session as done-while-away', () => {
    const status = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'idle',
      unseen: true,
      displayName: null,
    })
    expect(status.label).toBe('Done — while you were away')
    expect(status.pulse).toBe(true)
  })

  it('labels an unseen blocked session distinctly from a seen one', () => {
    const away = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'blocked',
      unseen: true,
      displayName: null,
    })
    expect(away.label).toBe('Blocked — while you were away')
    const seen = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'blocked',
      unseen: false,
      displayName: null,
    })
    expect(seen.label).toBe('Blocked — waiting on you')
  })

  it('labels an unseen error session as failed-while-away', () => {
    const status = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'error',
      unseen: true,
      displayName: null,
    })
    expect(status.label).toBe('Failed — while you were away')
  })

  it('ranks unseen sessions above ordinary ones but below the pinned favorite', () => {
    expect(sessionUrgencyRank({ theOne: false, idleState: 'idle', unseen: true })).toBeLessThan(
      sessionUrgencyRank({ theOne: false, idleState: 'idle', unseen: false })
    )
    expect(sessionUrgencyRank({ theOne: true, idleState: 'idle', unseen: true })).toBe(0)
  })
})
