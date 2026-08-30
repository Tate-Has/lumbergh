/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import ToastProvider from './ToastProvider'
import { useToast } from '../../hooks/toastContext'
import Toaster from './Toaster'

afterEach(cleanup)

function Harness({ onReady }: { onReady: (api: ReturnType<typeof useToast>) => void }) {
  const api = useToast()
  onReady(api)
  return <Toaster />
}

function mount() {
  let api!: ReturnType<typeof useToast>
  render(
    <ToastProvider>
      <Harness onReady={(a) => (api = a)} />
    </ToastProvider>
  )
  return () => api
}

describe('the toast surface', () => {
  it('shows an error with its actionable detail', () => {
    const api = mount()
    act(() => api().error("'feature' is already used by a worktree", '/src/aio-worktrees/feature'))

    expect(screen.getByTestId('toast-error')).toBeTruthy()
    expect(screen.getByText(/already used by a worktree/)).toBeTruthy()
    expect(screen.getByText('/src/aio-worktrees/feature')).toBeTruthy()
  })

  it('can be dismissed by hand, because an error may need to stay put', () => {
    const api = mount()
    act(() => api().error('boom'))

    fireEvent.click(screen.getByLabelText('Dismiss'))

    expect(screen.queryByTestId('toast-error')).toBeNull()
  })

  it('clears itself so a stale failure never lingers', () => {
    vi.useFakeTimers()
    try {
      const api = mount()
      act(() => api().error('boom'))
      expect(screen.queryByTestId('toast-error')).toBeTruthy()

      act(() => void vi.advanceTimersByTime(10000))

      expect(screen.queryByTestId('toast-error')).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('renders nothing at rest, so it never covers the terminal', () => {
    mount()
    expect(screen.queryByRole('status')).toBeNull()
  })
})
