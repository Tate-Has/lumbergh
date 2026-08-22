/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SessionNavigatorDots from './SessionNavigatorDots'

vi.mock('../hooks/useMediaQuery', () => ({ useIsDesktop: () => true }))

const payload = {
  sessions: [
    { name: 'api', alive: true, displayName: 'api', idleState: 'idle', role: 'session' },
    {
      name: 'docs',
      alive: true,
      displayName: 'docs',
      idleState: 'idle',
      role: 'session',
      workdir: '/src/docs',
    },
    {
      name: 'api-fix',
      alive: true,
      displayName: 'api-fix',
      idleState: 'working',
      role: 'worker',
      parent: 'api',
    },
    {
      name: 'docs-fix',
      alive: true,
      displayName: 'docs-fix',
      idleState: 'idle',
      role: 'worker',
      parent: 'a-session-that-died',
      worktreeParentRepo: '/src/docs',
    },
  ],
}

function renderDots() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => payload }))
  )
  return render(
    <MemoryRouter>
      <SessionNavigatorDots currentSessionName="api" />
    </MemoryRouter>
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('SessionNavigatorDots', () => {
  it('sits a worker bubble immediately right of its parent, ahead of other sessions', async () => {
    renderDots()

    await waitFor(() => expect(screen.getByRole('button', { name: 'AF' })).toBeTruthy())
    const labels = [...document.querySelectorAll('button')].map((b) => b.textContent)

    expect(labels).toEqual(['AP', 'AF', 'DO', 'DF'])
  })

  it('draws the worker smaller than the session it belongs to', async () => {
    renderDots()

    await waitFor(() => expect(screen.getByRole('button', { name: 'AF' })).toBeTruthy())

    expect(screen.getByRole('button', { name: 'AP' }).className).toContain('w-7 h-7')
    expect(screen.getByRole('button', { name: 'AF' }).className).toContain('w-5.5 h-5.5')
  })

  it('stands the bubbles on a shared floor so the small one hangs below', async () => {
    renderDots()

    await waitFor(() => expect(screen.getByRole('button', { name: 'AF' })).toBeTruthy())
    const row = screen.getByRole('button', { name: 'AF' }).closest('.flex.items-end')

    expect(row).not.toBeNull()
  })

  it('nests and names a worker whose spawning session died, via its repo', async () => {
    renderDots()

    await waitFor(() => expect(screen.getByRole('button', { name: 'DF' })).toBeTruthy())
    const labels = [...document.querySelectorAll('button')].map((b) => b.textContent)

    expect(labels).toEqual(['AP', 'AF', 'DO', 'DF'])
    expect(screen.getByText(/sub-session of docs/)).toBeTruthy()
  })

  it('names the parent in the worker tooltip', async () => {
    renderDots()

    await waitFor(() => expect(screen.getByRole('button', { name: 'AF' })).toBeTruthy())

    expect(screen.getByText(/sub-session of api/)).toBeTruthy()
  })
})
