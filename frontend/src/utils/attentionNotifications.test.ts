import { describe, it, expect } from 'vitest'
import { computeNotifications } from './attentionNotifications'

const ctx = { hidden: true, enabled: true, permissionGranted: true }
const s = (name: string, attentionState: 'idle' | 'blocked' | 'error' = 'idle') => ({
  name,
  displayName: null,
  unseen: true,
  attentionState,
})

describe('computeNotifications', () => {
  it('fires for a newly-unseen session with a deep link', () => {
    const { toFire, nextUnseen } = computeNotifications(new Set(), [s('foo')], ctx)
    expect(toFire).toHaveLength(1)
    expect(toFire[0].title).toBe('foo')
    expect(toFire[0].body).toBe('Done — while you were away')
    expect(toFire[0].tag).toBe('foo')
    expect(toFire[0].url).toBe('/session/foo')
    expect(nextUnseen.has('foo')).toBe(true)
  })

  it('uses the attention verb for blocked/error', () => {
    expect(computeNotifications(new Set(), [s('b', 'blocked')], ctx).toFire[0].body).toBe(
      'Blocked — while you were away'
    )
    expect(computeNotifications(new Set(), [s('e', 'error')], ctx).toFire[0].body).toBe(
      'Failed — while you were away'
    )
  })

  it('coalesces multiple newly-unseen into one dashboard notification', () => {
    const { toFire } = computeNotifications(new Set(), [s('a'), s('b'), s('c')], ctx)
    expect(toFire).toHaveLength(1)
    expect(toFire[0].body).toBe('3 sessions need your attention')
    expect(toFire[0].url).toBe('/')
    expect(toFire[0].tag).toBe('lumbergh-attention')
  })

  it('does not re-fire for a session already unseen last poll', () => {
    const { toFire } = computeNotifications(new Set(['foo']), [s('foo')], ctx)
    expect(toFire).toHaveLength(0)
  })

  it('fires again if a session cleared then became unseen again', () => {
    const first = computeNotifications(new Set(['foo']), [], ctx)
    expect(first.nextUnseen.has('foo')).toBe(false)
    const second = computeNotifications(first.nextUnseen, [s('foo')], ctx)
    expect(second.toFire).toHaveLength(1)
  })

  it('never fires when foreground, disabled, or permission not granted (but advances state)', () => {
    for (const bad of [
      { ...ctx, hidden: false },
      { ...ctx, enabled: false },
      { ...ctx, permissionGranted: false },
    ]) {
      const { toFire, nextUnseen } = computeNotifications(new Set(), [s('foo')], bad)
      expect(toFire).toHaveLength(0)
      expect(nextUnseen.has('foo')).toBe(true)
    }
  })

  it('ignores sessions that are not unseen', () => {
    const { toFire, nextUnseen } = computeNotifications(
      new Set(),
      [{ name: 'x', displayName: null, unseen: false, attentionState: null }],
      ctx
    )
    expect(toFire).toHaveLength(0)
    expect(nextUnseen.size).toBe(0)
  })
})
