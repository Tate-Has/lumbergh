import { describe, it, expect } from 'vitest'
import { isSessionCycleChord, exitsScrollMode } from './terminalChords'

const chord = (over: Partial<KeyboardEvent>) =>
  ({
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    key: '',
    code: '',
    type: 'keydown',
    ...over,
  }) as KeyboardEvent

describe('isSessionCycleChord', () => {
  it('claims Alt+Z so zen mode toggles instead of tmux seeing \\x1bz', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: 'z', code: 'KeyZ' }))).toBe(true)
  })

  it('claims Option+Z on macOS, where the key character is not "z"', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: 'Ω', code: 'KeyZ' }))).toBe(true)
  })

  it('claims the existing session-switch chords', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: 'ArrowLeft' }))).toBe(true)
    expect(isSessionCycleChord(chord({ altKey: true, key: 'ArrowRight' }))).toBe(true)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: '[' }))).toBe(true)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: ']' }))).toBe(true)
  })

  it('lets a bare z and Ctrl+Z through to the shell', () => {
    expect(isSessionCycleChord(chord({ key: 'z' }))).toBe(false)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: 'z', code: 'KeyZ' }))).toBe(false)
  })

  it('lets Alt+Meta+Z through, so OS chords are not swallowed', () => {
    expect(
      isSessionCycleChord(chord({ altKey: true, metaKey: true, key: 'z', code: 'KeyZ' }))
    ).toBe(false)
  })

  it('claims Alt+Arrow even with Meta held, as it did before the move', () => {
    expect(isSessionCycleChord(chord({ altKey: true, metaKey: true, key: 'ArrowLeft' }))).toBe(true)
    expect(isSessionCycleChord(chord({ altKey: true, metaKey: true, key: 'ArrowRight' }))).toBe(
      true
    )
  })

  it('claims Alt+V so the view toggle fires instead of tmux seeing \\x1bv', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: 'v', code: 'KeyV' }))).toBe(true)
  })

  it('claims Option+V on macOS, where the key character is not "v"', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: '√', code: 'KeyV' }))).toBe(true)
  })

  it('lets a bare v and Ctrl+V through to the shell', () => {
    expect(isSessionCycleChord(chord({ key: 'v', code: 'KeyV' }))).toBe(false)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: 'v', code: 'KeyV' }))).toBe(false)
  })
})

describe('exitsScrollMode', () => {
  it('exits on a plain character, so typing lands in the shell', () => {
    expect(exitsScrollMode(chord({ type: 'keydown', key: 'a' }))).toBe(true)
  })

  it('exits on Escape, which tmux would otherwise spend on the copy-mode selection', () => {
    expect(exitsScrollMode(chord({ type: 'keydown', key: 'Escape' }))).toBe(true)
  })

  it('ignores keyup and keypress, so one press does not send two q', () => {
    expect(exitsScrollMode(chord({ type: 'keyup', key: 'Escape' }))).toBe(false)
    expect(exitsScrollMode(chord({ type: 'keypress', key: 'a' }))).toBe(false)
  })

  it('leaves the copy-mode navigation keys alone', () => {
    expect(exitsScrollMode(chord({ type: 'keydown', key: 'ArrowUp' }))).toBe(false)
    expect(exitsScrollMode(chord({ type: 'keydown', key: 'PageUp' }))).toBe(false)
  })

  it('leaves modified keys alone', () => {
    expect(exitsScrollMode(chord({ type: 'keydown', key: 'a', ctrlKey: true }))).toBe(false)
    expect(exitsScrollMode(chord({ type: 'keydown', key: 'Escape', altKey: true }))).toBe(false)
  })
})
