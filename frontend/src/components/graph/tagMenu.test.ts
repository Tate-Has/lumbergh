import { describe, it, expect, vi, afterEach } from 'vitest'
import { buildTagMenuItems } from './tagMenu'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('buildTagMenuItems', () => {
  it('offers the origin delete only for a tag origin actually has', () => {
    const pushed = buildTagMenuItems('v0.20.0', new Set(['v0.20.0']), () => {})
    const localOnly = buildTagMenuItems('scratch', new Set(['v0.20.0']), () => {})

    expect(pushed.map((i) => i.label)).toEqual(['Delete tag', 'Delete tag on origin too'])
    expect(localOnly.map((i) => i.label)).toEqual(['Delete tag'])
  })

  it('offers only the local delete while origin has not answered yet', () => {
    const items = buildTagMenuItems('v0.20.0', null, () => {})

    expect(items.map((i) => i.label)).toEqual(['Delete tag'])
  })

  it('deletes locally without nagging', () => {
    const onDelete = vi.fn()
    const confirmSpy = vi.fn(() => true)
    vi.stubGlobal('confirm', confirmSpy)

    buildTagMenuItems('v0.20.0', new Set(['v0.20.0']), onDelete)[0].onClick()

    expect(onDelete).toHaveBeenCalledWith(false)
    expect(confirmSpy).not.toHaveBeenCalled()
  })

  it('confirms before touching origin, because that one is everyone elses', () => {
    const onDelete = vi.fn()
    vi.stubGlobal('confirm', () => false)
    const items = buildTagMenuItems('v0.20.0', new Set(['v0.20.0']), onDelete)

    items[1].onClick()
    expect(onDelete).not.toHaveBeenCalled()

    vi.stubGlobal('confirm', () => true)
    items[1].onClick()
    expect(onDelete).toHaveBeenCalledWith(true)
  })
})
