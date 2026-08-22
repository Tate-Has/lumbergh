/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { useState } from 'react'
import ErrorBoundary from './ErrorBoundary'

function Boom({ explode }: { explode: boolean }): React.ReactNode {
  if (explode) throw new Error('files is not iterable')
  return <div>panel content</div>
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('ErrorBoundary', () => {
  it('is invisible while nothing is wrong', () => {
    render(
      <ErrorBoundary>
        <Boom explode={false} />
      </ErrorBoundary>
    )

    expect(screen.getByText('panel content')).toBeTruthy()
    expect(screen.queryByTestId('error-boundary-fallback')).toBeNull()
  })

  it('shows the failure instead of a blank screen', () => {
    render(
      <ErrorBoundary label="The git view">
        <Boom explode />
      </ErrorBoundary>
    )

    expect(screen.getByTestId('error-boundary-fallback')).toBeTruthy()
    expect(screen.getByText(/The git view hit an error/)).toBeTruthy()
    expect(screen.getByText('files is not iterable')).toBeTruthy()
  })

  it('keeps everything outside it alive', () => {
    render(
      <div>
        <span>the terminal</span>
        <ErrorBoundary>
          <Boom explode />
        </ErrorBoundary>
      </div>
    )

    expect(screen.getByText('the terminal')).toBeTruthy()
  })

  it('can be retried once the cause is gone', () => {
    function Harness() {
      const [explode, setExplode] = useState(true)
      return (
        <>
          <button onClick={() => setExplode(false)}>fix it</button>
          <ErrorBoundary>
            <Boom explode={explode} />
          </ErrorBoundary>
        </>
      )
    }
    render(<Harness />)

    fireEvent.click(screen.getByText('fix it'))
    fireEvent.click(screen.getByText('Try again'))

    expect(screen.getByText('panel content')).toBeTruthy()
  })
})
