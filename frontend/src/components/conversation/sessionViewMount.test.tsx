/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest'
import { useEffect, useState } from 'react'
import { render, act } from '@testing-library/react'

let mountCount = 0

function FakeTerminal() {
  useEffect(() => {
    mountCount += 1
  }, [])
  return <div>terminal</div>
}

/** Mirrors the shape of SessionDetail's renderTerminal: both views always
 * mounted, the inactive one hidden with a class. */
function Pane({ view }: { view: 'term' | 'conv' }) {
  return (
    <div className="h-full relative">
      <div className={view === 'term' ? '' : 'hidden'}>
        <FakeTerminal />
      </div>
      <div className={view === 'conv' ? '' : 'hidden'}>conversation</div>
    </div>
  )
}

function Harness() {
  const [view, setView] = useState<'term' | 'conv'>('term')
  return (
    <>
      <button onClick={() => setView((v) => (v === 'term' ? 'conv' : 'term'))}>swap</button>
      <Pane view={view} />
    </>
  )
}

describe('session view swapping', () => {
  it('never remounts the terminal', () => {
    mountCount = 0
    const { getByText } = render(<Harness />)
    act(() => getByText('swap').click())
    act(() => getByText('swap').click())
    expect(mountCount).toBe(1)
  })
})
