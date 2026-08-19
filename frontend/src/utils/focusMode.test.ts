import { describe, it, expect } from 'vitest'
import { readStoredFocus, nextMainFocus, nextPanelFocus } from './focusMode'

describe('readStoredFocus', () => {
  it('reads a stored focus value', () => {
    expect(readStoredFocus('panel', null)).toBe('panel')
    expect(readStoredFocus('main', null)).toBe('main')
    expect(readStoredFocus('none', null)).toBe('none')
  })

  it('migrates a zen user with no focus key', () => {
    expect(readStoredFocus(null, 'true')).toBe('main')
    expect(readStoredFocus(null, 'false')).toBe('none')
  })

  it('prefers the focus key over the legacy zen key', () => {
    expect(readStoredFocus('panel', 'true')).toBe('panel')
  })

  it('treats anything unrecognized as none', () => {
    expect(readStoredFocus('sideways', null)).toBe('none')
    expect(readStoredFocus(null, null)).toBe('none')
  })
})

describe('nextMainFocus', () => {
  it('toggles main on and off', () => {
    expect(nextMainFocus('none')).toBe('main')
    expect(nextMainFocus('main')).toBe('none')
  })

  it('takes over from panel focus rather than clearing it', () => {
    expect(nextMainFocus('panel')).toBe('main')
  })
})

describe('nextPanelFocus', () => {
  it('toggles panel on and off', () => {
    expect(nextPanelFocus('none')).toBe('panel')
    expect(nextPanelFocus('panel')).toBe('none')
  })

  it('takes over from main focus', () => {
    expect(nextPanelFocus('main')).toBe('panel')
  })
})
