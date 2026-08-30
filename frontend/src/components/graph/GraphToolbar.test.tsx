/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import GraphToolbar from './GraphToolbar'

afterEach(cleanup)

const props = {
  mineOnly: false,
  mineAvailable: true,
  onToggleMineOnly: vi.fn(),
  search: '',
  onSearchChange: vi.fn(),
  matchCount: 0,
  searching: false,
  needsHistory: false,
  onStepMatch: vi.fn(),
  onSearchHistory: vi.fn(),
}

describe('GraphToolbar', () => {
  it('keeps the split pane free of the filter row until it is asked for', () => {
    render(<GraphToolbar {...props} />)

    expect(screen.queryByTestId('graph-search-input')).toBeNull()
    expect(screen.queryByTestId('graph-mine-toggle')).toBeNull()

    fireEvent.click(screen.getByTestId('graph-toolbar-toggle'))

    expect(screen.getByTestId('graph-search-input')).toBeTruthy()
    expect(screen.getByTestId('graph-mine-toggle')).toBeTruthy()
  })

  it('collapses back down again', () => {
    render(<GraphToolbar {...props} expandedByDefault />)

    fireEvent.click(screen.getByTestId('graph-toolbar-collapse'))

    expect(screen.queryByTestId('graph-search-input')).toBeNull()
  })

  it('opens with the filters showing in full screen', () => {
    render(<GraphToolbar {...props} expandedByDefault />)

    expect(screen.getByTestId('graph-search-input')).toBeTruthy()
  })

  it('re-applies the default when the pane enters and leaves full screen', () => {
    const { rerender } = render(<GraphToolbar {...props} />)
    expect(screen.queryByTestId('graph-search-input')).toBeNull()

    rerender(<GraphToolbar {...props} expandedByDefault />)
    expect(screen.getByTestId('graph-search-input')).toBeTruthy()

    rerender(<GraphToolbar {...props} expandedByDefault={false} />)
    expect(screen.queryByTestId('graph-search-input')).toBeNull()
  })

  it('marks the collapsed button when a filter is still on', () => {
    render(<GraphToolbar {...props} mineOnly />)

    expect(screen.getByTestId('graph-toolbar-active-dot')).toBeTruthy()
  })
})
