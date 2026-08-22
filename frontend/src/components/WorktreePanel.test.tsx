/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import WorktreePanel from './WorktreePanel'

const payload = {
  worktrees: [
    {
      path: '/home/dev/tools-worktrees/new_instance',
      repo: 'tools',
      branch: 'new_instance',
      session: null,
      agent: null,
      state: 'orphan',
      task_intent: 'stand up a second instance',
    },
    {
      path: '/home/dev/lumbergh-worktrees/live',
      repo: 'lumbergh',
      branch: 'live',
      session: 'live',
      agent: 'claude-code',
      state: 'active',
      task_intent: null,
    },
  ],
}

function renderPanel() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => payload }))
  )
  return render(<WorktreePanel />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('WorktreePanel', () => {
  it('names the repo an orphaned worktree came from', async () => {
    renderPanel()

    await waitFor(() => expect(screen.getByText('new_instance')).toBeTruthy())

    expect(screen.getByText(/from tools/)).toBeTruthy()
  })

  it('shows what the orphan was spawned to do', async () => {
    renderPanel()

    await waitFor(() => expect(screen.getByText('new_instance')).toBeTruthy())

    expect(screen.getByText('stand up a second instance')).toBeTruthy()
  })
})
