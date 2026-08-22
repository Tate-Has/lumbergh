import { describe, it, expect, vi, afterEach } from 'vitest'
import { resetMenuEntries, confirmHardReset } from './resetMenu'
import { buildBranchMenuItems } from './branchMenu'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('resetMenuEntries', () => {
  it('offers hard first, because that is the reset this workflow reaches for', () => {
    const entries = resetMenuEntries(
      () => {},
      () => {}
    )

    expect(entries.map((e) => e.label)).toEqual(['Reset hard to here', 'Reset soft to here'])
  })

  it('marks only the destructive one as danger', () => {
    const [hard, soft] = resetMenuEntries(
      () => {},
      () => {}
    )

    expect(hard.danger).toBe(true)
    expect(soft.danger).toBe(false)
  })

  it('wires each entry to its own handler', () => {
    const onHard = vi.fn()
    const onSoft = vi.fn()
    const [hard, soft] = resetMenuEntries(onHard, onSoft)

    hard.onClick()
    expect(onHard).toHaveBeenCalledOnce()
    expect(onSoft).not.toHaveBeenCalled()

    soft.onClick()
    expect(onSoft).toHaveBeenCalledOnce()
  })
})

describe('confirmHardReset', () => {
  it('names the target and spells out what is destroyed', () => {
    const confirmSpy = vi.fn((_message: string) => true)
    vi.stubGlobal('confirm', confirmSpy)

    expect(confirmHardReset('27bb825')).toBe(true)
    const [prompt] = confirmSpy.mock.calls[0]
    expect(prompt).toContain('27bb825')
    expect(prompt).toContain('DESTROY')
  })

  it('reports a declined confirm', () => {
    vi.stubGlobal('confirm', () => false)

    expect(confirmHardReset('27bb825')).toBe(false)
  })
})

describe('the branch menu', () => {
  const remoteOnly = {
    name: 'origin/main',
    commitHash: '27bb825a4c55',
    commitShortHash: '27bb825',
    local: false,
    remote: true,
    x: 0,
    y: 0,
  }

  const build = (handleResetTo: (hash: string, mode: 'soft' | 'hard') => void) =>
    buildBranchMenuItems(
      remoteOnly,
      false,
      false,
      () => {},
      () => {},
      handleResetTo,
      () => {},
      () => {}
    )

  it('offers hard then soft where it used to offer one silently-soft reset', () => {
    const labels = build(() => {})
      .map((i) => i.label)
      .filter((l) => typeof l === 'string' && l.includes('Reset'))

    expect(labels).toEqual(['Reset hard to here', 'Reset soft to here'])
  })

  it('resets hard only once the destructive confirm is accepted', () => {
    const resetTo = vi.fn()
    vi.stubGlobal('confirm', () => false)
    const hard = build(resetTo).find((i) => i.key === 'reset-hard')!

    hard.onClick()
    expect(resetTo).not.toHaveBeenCalled()

    vi.stubGlobal('confirm', () => true)
    hard.onClick()
    expect(resetTo).toHaveBeenCalledWith('27bb825a4c55', 'hard')
  })

  it('sends soft as soft', () => {
    const resetTo = vi.fn()
    vi.stubGlobal('confirm', () => true)

    build(resetTo)
      .find((i) => i.key === 'reset-soft')!
      .onClick()

    expect(resetTo).toHaveBeenCalledWith('27bb825a4c55', 'soft')
  })
})
