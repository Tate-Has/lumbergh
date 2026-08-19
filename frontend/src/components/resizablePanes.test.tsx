/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import ResizablePanes from './ResizablePanes'

// vitest.config.ts does not set `globals: true`, so @testing-library/react's
// auto-cleanup (which detects a global `afterEach`) never registers. Each
// `render` call in this file would otherwise leave its DOM behind for the
// next test.
afterEach(cleanup)

const panes = (collapse: 'left' | 'right' | null) => (
  <ResizablePanes
    collapse={collapse}
    left={<div data-testid="left-child">left</div>}
    right={<div data-testid="right-child">right</div>}
  />
)

describe('ResizablePanes collapse', () => {
  it('renders both panes when nothing is collapsed', () => {
    const { queryByTestId } = render(panes(null))
    expect(queryByTestId('left-child')).not.toBeNull()
    expect(queryByTestId('right-child')).not.toBeNull()
    const leftPane = queryByTestId('left-child')!.closest('[data-pane="left"]') as HTMLElement
    expect(leftPane.style.width).toBe('50%')
    const rightPane = queryByTestId('right-child')!.parentElement as HTMLElement
    expect(rightPane.style.width).toBe('50%')
  })

  it('drops the right pane from the DOM when collapsing right', () => {
    const { queryByTestId } = render(panes('right'))
    expect(queryByTestId('left-child')).not.toBeNull()
    expect(queryByTestId('right-child')).toBeNull()
    const leftPane = queryByTestId('left-child')!.closest('[data-pane="left"]') as HTMLElement
    expect(leftPane.style.width).toBe('100%')
  })

  it('keeps the left pane MOUNTED but hidden when collapsing left', () => {
    // The left pane holds the terminal: a live PTY, a WebSocket and scrollback.
    // Unmounting it reconnects the session, so it must stay in the DOM.
    const { queryByTestId } = render(panes('left'))
    expect(queryByTestId('right-child')).not.toBeNull()
    const leftChild = queryByTestId('left-child')
    expect(leftChild).not.toBeNull()
    expect(leftChild!.closest('[data-pane="left"]')).toHaveProperty('style.display', 'none')
    const rightPane = queryByTestId('right-child')!.parentElement as HTMLElement
    expect(rightPane.style.width).toBe('100%')
  })
})
