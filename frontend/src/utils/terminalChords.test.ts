import { describe, it, expect } from 'vitest'
import { isSessionCycleChord } from './terminalChords'

const chord = (over: Partial<KeyboardEvent>) =>
  ({ altKey: false, ctrlKey: false, metaKey: false, key: '', ...over }) as KeyboardEvent

describe('isSessionCycleChord', () => {
  it('claims Alt+Z so zen mode toggles instead of tmux seeing \\x1bz', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: 'z' }))).toBe(true)
  })

  it('claims the existing session-switch chords', () => {
    expect(isSessionCycleChord(chord({ altKey: true, key: 'ArrowLeft' }))).toBe(true)
    expect(isSessionCycleChord(chord({ altKey: true, key: 'ArrowRight' }))).toBe(true)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: '[' }))).toBe(true)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: ']' }))).toBe(true)
  })

  it('lets a bare z and Ctrl+Z through to the shell', () => {
    expect(isSessionCycleChord(chord({ key: 'z' }))).toBe(false)
    expect(isSessionCycleChord(chord({ ctrlKey: true, key: 'z' }))).toBe(false)
  })

  it('lets Alt+Meta+Z through, so OS chords are not swallowed', () => {
    expect(isSessionCycleChord(chord({ altKey: true, metaKey: true, key: 'z' }))).toBe(false)
  })

  it('claims Alt+Arrow even with Meta held, as it did before the move', () => {
    expect(isSessionCycleChord(chord({ altKey: true, metaKey: true, key: 'ArrowLeft' }))).toBe(true)
    expect(isSessionCycleChord(chord({ altKey: true, metaKey: true, key: 'ArrowRight' }))).toBe(
      true
    )
  })
})
