/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render } from '@testing-library/react'
import ConversationView from './ConversationView'

vi.mock('../../hooks/useConversationSocket', () => ({
  useConversationSocket: () => ({
    items: Array.from({ length: 500 }, (_, i) => ({
      id: String(i),
      type: 'status' as const,
      text: `event ${i}`,
    })),
    noTranscript: false,
    isConnected: true,
  }),
}))

// jsdom lays nothing out, so every element reports offsetHeight 0 and the
// virtualizer sees a zero-height viewport (and renders nothing at all). Give
// the scroll container a viewport so the window it computes is a real one.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    value: 600,
  })
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})

// Windowing only. The ResizeObserver stub never fires, so no row ever measures
// and every one keeps the 80px estimate — dynamic heights, and the follow
// behaviour that rides on them, need a real browser.
describe('ConversationView', () => {
  it('renders a window of rows, not all 500', () => {
    const { container } = render(<ConversationView sessionName="x" scale={1} />)
    const rendered = container.querySelectorAll('[data-index]')
    expect(rendered.length).toBeGreaterThan(0)
    expect(rendered.length).toBeLessThan(100)
  })
})
