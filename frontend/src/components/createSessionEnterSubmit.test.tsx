/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CreateSessionModal from './CreateSessionModal'

const REPO = { path: '/home/dev/myproject', name: 'myproject' }

function stubBackend() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/settings')) return jsonResponse({})
    if (url.includes('/directories/search')) return jsonResponse({ directories: [REPO] })
    if (url.includes('/sessions') && init?.method === 'POST')
      return jsonResponse({ name: 'myproject' })
    return jsonResponse({})
  })
}

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, json: async () => body, text: async () => '' } as Response
}

function postCalls(fetchMock: ReturnType<typeof stubBackend>) {
  return fetchMock.mock.calls.filter(
    ([url, init]) => String(url).endsWith('/sessions') && (init as RequestInit)?.method === 'POST'
  )
}

async function openModalAndPickRepo() {
  render(
    <MemoryRouter>
      <CreateSessionModal onClose={() => {}} onCreated={() => {}} />
    </MemoryRouter>
  )
  fireEvent.focus(screen.getByPlaceholderText('Search git repositories...'))
  await act(async () => {
    vi.advanceTimersByTime(400)
  })
  fireEvent.click(await screen.findByText(REPO.name))
  await waitFor(() => expect(screen.getByText(REPO.path)).toBeTruthy())
}

let fetchMock: ReturnType<typeof stubBackend>

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  fetchMock = stubBackend()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('creating a session with the keyboard', () => {
  it('submits on Enter after the repo was picked by a click that took focus with it', async () => {
    await openModalAndPickRepo()

    fireEvent.keyDown(document.body, { key: 'Enter', bubbles: true })

    await waitFor(() => expect(postCalls(fetchMock)).toHaveLength(1))
  })

  it('leaves Enter inside a field to the form, so a submit is not doubled', async () => {
    await openModalAndPickRepo()

    // jsdom does not implement implicit form submission, so the browser's own
    // Enter-submits-the-form is invisible here: zero POSTs means we stayed out.
    fireEvent.keyDown(screen.getByTestId('session-name-input'), { key: 'Enter', bubbles: true })

    await act(async () => {})
    expect(postCalls(fetchMock)).toHaveLength(0)
  })
})
