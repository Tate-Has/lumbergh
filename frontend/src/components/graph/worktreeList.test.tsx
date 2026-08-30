/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import WorktreeList from './WorktreeList'
import { describeLoss } from '../../utils/reapLoss'
import ToastProvider from '../ui/ToastProvider'
import type { Worktree } from '../../hooks/useWorktrees'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const wt = (over: Partial<Worktree> = {}): Worktree => ({
  path: '/home/jim/src/aio-worktrees/feature',
  repo: 'aio',
  parent_repo: '/home/jim/src/aio',
  branch: 'feature',
  session: null,
  agent: null,
  task_intent: null,
  state: 'orphan',
  ...over,
})

function mount(worktrees: Worktree[], onChanged = vi.fn(), currentSession?: string) {
  render(
    <ToastProvider>
      <WorktreeList worktrees={worktrees} onChanged={onChanged} currentSession={currentSession} />
    </ToastProvider>
  )
  return onChanged
}

describe('what the worktree list shows', () => {
  it('names the branch each worktree holds, which is the whole point', () => {
    mount([wt()])
    expect(screen.getByText('feature')).toBeTruthy()
  })

  it('shortens the home prefix so the path stays readable on a phone', () => {
    mount([wt()])
    expect(screen.getByText('~/src/aio-worktrees/feature')).toBeTruthy()
  })

  it('marks a worktree with no live session', () => {
    mount([wt()])
    expect(screen.getByText('no session')).toBeTruthy()
  })

  it('refuses to offer removal of the worktree you are working in', () => {
    mount([wt({ session: 'mine', state: 'active' })], vi.fn(), 'mine')
    expect(screen.getByText('you are here')).toBeTruthy()
    expect((screen.getByTestId('worktree-remove-feature') as HTMLButtonElement).disabled).toBe(true)
  })

  it('says so plainly when there are none', () => {
    mount([])
    expect(screen.getByText(/No worktrees/)).toBeTruthy()
  })
})

describe('removing a worktree', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
  })

  it('reaps without force first, and reloads the list on success', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ json: async () => ({ status: 'removed' }) })
    vi.stubGlobal('fetch', fetchMock)
    const onChanged = mount([wt()])

    fireEvent.click(screen.getByTestId('worktree-remove-feature'))

    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      path: '/home/jim/src/aio-worktrees/feature',
      force: false,
    })
  })

  it('asks before forcing, and keeps the worktree when the answer is no', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ json: async () => ({ error: 'dirty', reason: 'dirty' }) })
    vi.stubGlobal('fetch', fetchMock)
    const onChanged = mount([wt()])

    fireEvent.click(screen.getByTestId('worktree-remove-feature'))

    await waitFor(() => expect(window.confirm).toHaveBeenCalled())
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('forces only after the confirm is accepted', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ json: async () => ({ error: 'dirty', reason: 'dirty' }) })
      .mockResolvedValueOnce({ json: async () => ({ status: 'removed' }) })
    vi.stubGlobal('fetch', fetchMock)
    const onChanged = mount([wt()])

    fireEvent.click(screen.getByTestId('worktree-remove-feature'))

    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).force).toBe(true)
  })

  it('tells the confirm what will actually be lost', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ json: async () => ({ error: 'x', reason: 'unlanded', commits: 2 }) })
    vi.stubGlobal('fetch', fetchMock)
    mount([wt()])

    fireEvent.click(screen.getByTestId('worktree-remove-feature'))

    return waitFor(() => expect(vi.mocked(window.confirm).mock.calls[0][0]).toContain('2 commits'))
  })
})

describe('naming the loss', () => {
  it('never invents a count it was not given', () => {
    expect(describeLoss({ reason: 'dirty' })).toContain('uncommitted')
    expect(describeLoss({ reason: 'dirty' })).not.toMatch(/\d/)
  })

  it('counts commits, and gets the singular right', () => {
    expect(describeLoss({ reason: 'unlanded', commits: 1 })).toContain('1 commit here is')
    expect(describeLoss({ reason: 'unlanded', commits: 3 })).toContain('3 commits')
  })

  it('admits when landedness could not be established', () => {
    expect(describeLoss({ reason: 'unknown' })).toContain('could not be established')
  })
})
