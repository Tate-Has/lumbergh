import { describe, it, expect } from 'vitest'
import { readStoredFocus, nextMainFocus, nextPanelFocus, paneLayout } from './focusMode'

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

describe('paneLayout', () => {
  it('splits the viewport when nothing is maximized', () => {
    expect(paneLayout('none', 'panel', false)).toMatchObject({
      maximized: false,
      terminalVisible: true,
      collapse: null,
    })
  })

  it('gives the panel the viewport and hides the terminal', () => {
    expect(paneLayout('panel', 'panel', false)).toMatchObject({
      maximized: true,
      terminalMaximized: false,
      terminalVisible: false,
      collapse: 'left',
    })
  })

  it('keeps the strip up when the maximized pane is the terminal', () => {
    expect(paneLayout('panel', 'terminal', false)).toMatchObject({
      maximized: true,
      terminalMaximized: true,
      terminalVisible: true,
      collapse: 'right',
    })
  })

  it('has nothing to maximize when every panel is hidden', () => {
    expect(paneLayout('panel', 'panel', true)).toMatchObject({
      maximized: false,
      terminalVisible: true,
      collapse: 'right',
    })
  })

  it('drops the strip in zen, whichever pane was last maximized', () => {
    for (const pane of ['panel', 'terminal'] as const) {
      expect(paneLayout('main', pane, false)).toMatchObject({
        maximized: false,
        collapse: 'right',
      })
    }
  })
})
