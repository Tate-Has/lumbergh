import { describe, it, expect } from 'vitest'
import {
  getSessionStatus,
  statusColorClasses,
  sessionUrgencyRank,
  parseSessionsPayload,
} from './sessionStatus'

describe('parseSessionsPayload', () => {
  it('unwraps the { sessions: [...] } shape the API actually returns', () => {
    const sessions = parseSessionsPayload({
      sessions: [{ name: 'issue-669', alive: true, idleState: 'idle', displayName: null }],
    })
    expect(sessions.map((s) => s.name)).toEqual(['issue-669'])
  })

  it('still accepts a bare array', () => {
    const sessions = parseSessionsPayload([{ name: 'a', alive: true, displayName: null }])
    expect(sessions).toHaveLength(1)
  })

  it('falls back to empty for malformed payloads', () => {
    expect(parseSessionsPayload(null)).toEqual([])
    expect(parseSessionsPayload({})).toEqual([])
  })
})

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

  it('does not let an unknown state pass for a working one', () => {
    const unknown = getSessionStatus({
      name: 's',
      alive: true,
      idleState: null,
      displayName: null,
    })
    expect(unknown.color).toBe('gray')
    expect(unknown.label).toBe('Unknown')
    expect(statusColorClasses.gray).toBeDefined()
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
    expect(sessionUrgencyRank({ theOne: false, idleState: 'working' })).toBe(2)
    expect(sessionUrgencyRank({ idleState: 'idle' })).toBe(2)
  })

  it('does not let "done while you were away" outrank a session you just used', () => {
    // Finished-while-away is worth a badge, not a place above the session in
    // front of you: promoting it buried whatever you touched most recently at
    // the bottom of the dashboard.
    expect(sessionUrgencyRank({ unseen: true, idleState: 'idle' })).toBe(
      sessionUrgencyRank({ idleState: 'idle' })
    )
  })

  it('still floats a session that is actually waiting on a human', () => {
    expect(sessionUrgencyRank({ needsAnswer: true })).toBe(1)
    expect(sessionUrgencyRank({ idleState: 'blocked', unseen: true })).toBe(1)
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

  it('keeps the pinned favorite on top even when it has unseen work', () => {
    expect(sessionUrgencyRank({ theOne: true, idleState: 'idle', unseen: true })).toBe(0)
  })

  it('leaves an unseen session ranked with its peers, so recency decides', () => {
    expect(sessionUrgencyRank({ theOne: false, idleState: 'idle', unseen: true })).toBe(
      sessionUrgencyRank({ theOne: false, idleState: 'idle', unseen: false })
    )
  })
})

describe('needs-answer (cheap-LLM question detection) overlay', () => {
  it('labels an idle session with a detected question as waiting on you', () => {
    const status = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'idle',
      needsAnswer: true,
      displayName: null,
    })
    expect(status.color).toBe('purple')
    expect(status.pulse).toBe(true)
    expect(status.label).toBe('Question — waiting on you')
  })

  it('labels an unseen needs-answer session as a question-while-away', () => {
    const status = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'idle',
      needsAnswer: true,
      unseen: true,
      displayName: null,
    })
    expect(status.label).toBe('Question — while you were away')
  })

  it('lets a structural blocked state win over an inferred question', () => {
    const status = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'blocked',
      needsAnswer: true,
      displayName: null,
    })
    expect(status.label).toBe('Blocked — waiting on you')
  })

  it('ignores a stale needs-answer flag once the session is working again', () => {
    const status = getSessionStatus({
      name: 's',
      alive: true,
      idleState: 'working',
      needsAnswer: true,
      displayName: null,
    })
    expect(status.label).toBe('Working')
  })

  it('ranks a needs-answer session level with blocked, above unseen', () => {
    expect(sessionUrgencyRank({ idleState: 'idle', needsAnswer: true })).toBe(1)
    expect(sessionUrgencyRank({ idleState: 'idle', needsAnswer: true })).toBeLessThan(
      sessionUrgencyRank({ idleState: 'idle', unseen: true })
    )
  })
})
