/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'

const socket = {
  items: [{ id: '1', type: 'agent_message', text: 'hello' }],
  isConnected: true,
  noTranscript: false,
  remaining: 0,
  loadingOlder: false,
  loadOlder: vi.fn(),
}

vi.mock('../../hooks/useConversationSocket', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useConversationSocket: () => socket,
}))
vi.mock('../../hooks/useTheme', () => ({ useTheme: () => ({ theme: 'dark' }) }))

// jsdom has no ResizeObserver; the view observes its scroller for zoom changes.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver

import ConversationView from './ConversationView'

beforeEach(() => {
  socket.remaining = 0
  socket.loadingOlder = false
  socket.loadOlder = vi.fn()
})
afterEach(cleanup)

describe('the door to older history', () => {
  it('stays shut when the whole transcript is already on screen', () => {
    render(<ConversationView sessionName="s" />)

    expect(screen.queryByTestId('load-older')).toBeNull()
  })

  it('offers what is still behind, with a count', () => {
    socket.remaining = 1646
    render(<ConversationView sessionName="s" />)

    expect(screen.getByTestId('load-older').textContent).toContain('1646 more')
  })

  it('asks for the previous page when clicked', () => {
    socket.remaining = 1646
    render(<ConversationView sessionName="s" />)

    fireEvent.click(screen.getByTestId('load-older'))

    expect(socket.loadOlder).toHaveBeenCalledOnce()
  })

  it('cannot be asked twice while a page is in flight', () => {
    socket.remaining = 1646
    socket.loadingOlder = true
    render(<ConversationView sessionName="s" />)

    const button = screen.getByTestId('load-older') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(button.textContent).toContain('Loading')
  })
})
