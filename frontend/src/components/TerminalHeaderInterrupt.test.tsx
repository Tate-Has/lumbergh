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
      headerExpanded={false}
      onHeaderExpandedChange={noop}
      isTouchDevice
      onSendRaw={noop}
      onSendViaApi={noop}
      onSendTmuxCommand={noop}
      onInterrupt={noop}
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

describe('the Esc button', () => {
  it('interrupts the agent', () => {
    const onInterrupt = vi.fn()
    renderHeader({ onInterrupt })

    screen.getByTestId('interrupt-btn').click()

    expect(onInterrupt).toHaveBeenCalledTimes(1)
  })

  it('still stops the agent while the terminal socket is reconnecting', () => {
    const onInterrupt = vi.fn()
    renderHeader({ onInterrupt, isConnected: false })

    const btn = screen.getByTestId('interrupt-btn') as HTMLButtonElement
    expect(btn.disabled).toBe(false)

    btn.click()

    expect(onInterrupt).toHaveBeenCalledTimes(1)
  })
})
