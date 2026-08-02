import { describe, it, expect } from 'vitest'
import { canBabysit } from './babysit'

describe('canBabysit', () => {
  it('offers the toggle on a live top-level session', () => {
    expect(canBabysit({ role: 'session', type: 'direct', alive: true }, false)).toBe(true)
  })

  it('never offers it on a worker or on Bill', () => {
    expect(canBabysit({ role: 'worker', alive: true }, false)).toBe(false)
    expect(canBabysit({ role: 'bill', alive: true }, false)).toBe(false)
  })

  it('never offers it on a scratch session', () => {
    expect(canBabysit({ role: 'session', type: 'scratch', alive: true }, false)).toBe(false)
  })

  it('hides it on a dead session that is not babysat', () => {
    expect(canBabysit({ role: 'session', alive: false }, false)).toBe(false)
  })

  it('keeps it on a dead session that is still babysat, so the loop stays stoppable', () => {
    expect(canBabysit({ role: 'session', alive: false }, true)).toBe(true)
  })
})
