/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import SharedFiles from './SharedFiles'

const DAY = 86400
const midnight = new Date(new Date().setHours(0, 0, 0, 0)).getTime() / 1000

const files = [
  { name: 'fresh.md', size: 10, modified: midnight + 3600 },
  { name: 'yesterday.md', size: 10, modified: midnight - 3600 },
  { name: 'ancient.md', size: 10, modified: midnight - 30 * DAY },
]

function renderPanel() {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === 'DELETE') return { ok: true, json: async () => ({ deleted: 2 }) }
    return { ok: true, json: async () => ({ files }) }
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<SharedFiles />)
  return fetchMock
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('SharedFiles date-group deletion', () => {
  it('offers a delete control on every group separator but Today', async () => {
    renderPanel()

    await waitFor(() => expect(screen.getByText('fresh.md')).toBeTruthy())

    const titles = screen.getAllByTitle(/^Delete everything/).map((b) => b.getAttribute('title'))
    expect(titles).toEqual([
      'Delete everything from Yesterday and older',
      'Delete everything older than a week',
    ])
  })

  it('deletes from that group down, after confirming the count', async () => {
    const fetchMock = renderPanel()
    vi.stubGlobal(
      'confirm',
      vi.fn(() => true)
    )

    await waitFor(() => expect(screen.getByText('fresh.md')).toBeTruthy())
    screen.getByTitle('Delete everything from Yesterday and older').click()

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            init?.method === 'DELETE' &&
            String(url).endsWith(`/shared/files?older_than=${midnight}`)
        )
      ).toBe(true)
    )
    expect(vi.mocked(confirm).mock.calls[0][0]).toContain('Delete 2 shared files from "Yesterday"')
  })

  it('deletes nothing when the confirm is dismissed', async () => {
    const fetchMock = renderPanel()
    vi.stubGlobal(
      'confirm',
      vi.fn(() => false)
    )

    await waitFor(() => expect(screen.getByText('fresh.md')).toBeTruthy())
    screen.getByTitle('Delete everything older than a week').click()

    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
  })
})
