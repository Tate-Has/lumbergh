/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import BillHarnessMissing from './BillHarnessMissing'
import { isHarnessMissing } from '../utils/billHarness'

afterEach(cleanup)

const detail = {
  stage: 'harness',
  error: 'the `pi` harness binary `pi` is not installed',
  harness: 'pi',
  binary: 'pi',
  install_url: 'https://example.test/pi',
  why: 'Bill polls the fleet continuously, so he runs on a cheap local model.',
  fallback_agent: 'claude-code',
}

describe('the missing-harness recovery dialog', () => {
  it('names the harness and links somewhere to install it', () => {
    render(<BillHarnessMissing detail={detail} onClose={() => {}} onUseFallback={() => {}} />)

    expect(screen.getByText(/Bill needs the pi harness/)).toBeTruthy()
    const link = screen.getByTestId('bill-harness-install-link') as HTMLAnchorElement
    expect(link.href).toContain('example.test/pi')
  })

  it('offers the configured agent as a way to run Bill right now', () => {
    const onUseFallback = vi.fn()
    render(<BillHarnessMissing detail={detail} onClose={() => {}} onUseFallback={onUseFallback} />)

    fireEvent.click(screen.getByTestId('bill-harness-use-fallback'))

    expect(onUseFallback).toHaveBeenCalledWith('claude-code')
  })

  it('says what the fallback costs rather than switching silently', () => {
    render(<BillHarnessMissing detail={detail} onClose={() => {}} onUseFallback={() => {}} />)

    expect(screen.getByText(/will cost more/)).toBeTruthy()
  })

  it('asks for a default agent when there is none to fall back to', () => {
    render(
      <BillHarnessMissing
        detail={{ ...detail, fallback_agent: null }}
        onClose={() => {}}
        onUseFallback={() => {}}
      />
    )

    expect(screen.queryByTestId('bill-harness-use-fallback')).toBeNull()
    expect(screen.getByText(/Set a default agent in Settings/)).toBeTruthy()
  })
})

describe('recognising the failure', () => {
  it('claims only harness-stage failures that name a harness', () => {
    expect(isHarnessMissing(detail)).toBe(true)
    expect(isHarnessMissing({ stage: 'tmux', error: 'nope' })).toBe(false)
    expect(isHarnessMissing({ stage: 'harness' })).toBe(false)
    expect(isHarnessMissing('a plain string error')).toBe(false)
    expect(isHarnessMissing(null)).toBe(false)
  })
})
