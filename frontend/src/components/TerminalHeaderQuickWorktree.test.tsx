/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import TerminalHeader from './TerminalHeader'

const noop = () => {}

function renderHeader(props: Record<string, unknown> = {}) {
  return render(
    <TerminalHeader
      sessionName="lumbergh"
      isConnected
      fontSize={14}
      onFontSizeChange={noop}
      headerExpanded
      onHeaderExpandedChange={noop}
      isTouchDevice={false}
      onSendRaw={noop}
      onSendViaApi={noop}
      onSendTmuxCommand={noop}
      onFit={noop}
      showSessionDots={false}
      view="term"
      onToggleView={noop}
      scale={1}
      onScaleChange={noop}
      {...props}
    />
  )
}

afterEach(cleanup)

describe('the quick worktree button', () => {
  it('is offered alongside the deliberate New Session button', () => {
    const onQuickWorktree = vi.fn()
    renderHeader({ onQuickWorktree, onSpawnSession: noop })

    screen.getByTestId('quick-worktree').click()

    expect(onQuickWorktree).toHaveBeenCalledTimes(1)
  })

  it('stays out of the way when the session has no repo to branch', () => {
    renderHeader()

    expect(screen.queryByTestId('quick-worktree')).toBeNull()
  })
})
