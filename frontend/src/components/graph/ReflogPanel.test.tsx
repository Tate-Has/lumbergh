/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import ReflogPanel, { ReflogOverlay } from './ReflogPanel'

const entries = [
  {
    hash: 'a'.repeat(40),
    shortHash: 'aaaaaaa',
    selector: 'HEAD@{0}',
    action: 'reset',
    message: 'reset: moving to HEAD~2',
    relativeDate: '2 minutes ago',
  },
  {
    hash: 'b'.repeat(40),
    shortHash: 'bbbbbbb',
    selector: 'HEAD@{1}',
    action: 'commit',
    message: 'commit: the work I just lost',
    relativeDate: '5 minutes ago',
  },
]

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ entries }), { status: 200 }))
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ReflogPanel', () => {
  it('shows the commit the graph can no longer reach', async () => {
    render(
      <ReflogPanel sessionName="s" onClose={vi.fn()} onBranchFrom={vi.fn()} onResetTo={vi.fn()} />
    )

    await waitFor(() => expect(screen.getAllByTestId('reflog-entry')).toHaveLength(2))
    expect(screen.getByText('commit: the work I just lost')).toBeTruthy()
    expect(screen.getByText('HEAD@{1}')).toBeTruthy()
  })

  it('offers to branch from an entry, which is the non-destructive way back', async () => {
    const onBranchFrom = vi.fn()
    render(
      <ReflogPanel
        sessionName="s"
        onClose={vi.fn()}
        onBranchFrom={onBranchFrom}
        onResetTo={vi.fn()}
      />
    )
    await waitFor(() => screen.getAllByTestId('reflog-entry'))

    fireEvent.click(screen.getAllByTitle(/Create a branch here/)[1])

    expect(onBranchFrom).toHaveBeenCalledWith(entries[1])
  })

  it('says so rather than hanging when the reflog cannot be read', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('nope', { status: 500 }))
    )
    render(
      <ReflogPanel sessionName="s" onClose={vi.fn()} onBranchFrom={vi.fn()} onResetTo={vi.fn()} />
    )

    await waitFor(() => expect(screen.getByText(/Could not read the reflog/)).toBeTruthy())
  })
})

describe('ReflogOverlay', () => {
  it('stays unmounted — and asks the API for nothing — until opened', () => {
    render(
      <ReflogOverlay
        open={false}
        sessionName="s"
        onClose={vi.fn()}
        onBranchFrom={vi.fn()}
        onResetTo={vi.fn()}
      />
    )

    expect(screen.queryByTestId('reflog-panel')).toBeNull()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('has nothing to read without a session', () => {
    render(<ReflogOverlay open onClose={vi.fn()} onBranchFrom={vi.fn()} onResetTo={vi.fn()} />)

    expect(screen.queryByTestId('reflog-panel')).toBeNull()
  })
})
