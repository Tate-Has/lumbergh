/**
 * @vitest-environment jsdom
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
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

/** Reproduces the mount-persistence PATTERN Terminal.tsx is supposed to
 * follow (both views always mounted, the inactive one hidden with a class) —
 * NOT a copy of Terminal.tsx itself. This alone would stay green even if
 * Terminal.tsx regressed to conditionally mounting the xterm container, which
 * is why the 'terminal-container stays mounted' test below reads the real
 * source and fails on that specific regression shape. */
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

describe('session view swapping (pattern)', () => {
  it('never remounts the terminal', () => {
    mountCount = 0
    const { getByText } = render(<Harness />)
    act(() => getByText('swap').click())
    act(() => getByText('swap').click())
    expect(mountCount).toBe(1)
  })
})

// Guards the real Terminal.tsx source directly. Mounting the actual component
// requires stubbing xterm, its addons, and two live WebSocket connections
// (terminal stream + conversation activity feed) plus ResizeObserver/
// matchMedia — deep enough into browser-only territory that a source-shape
// check is the more honest and more maintainable guard against this specific,
// twice-repeated regression: someone changing the xterm container div from
// "always rendered, hidden via class" to "conditionally rendered on `view`",
// which would unmount xterm (and its WebSocket) on every view swap.
describe('session view swapping (Terminal.tsx source)', () => {
  const terminalSource = readFileSync(
    path.resolve(process.cwd(), 'src/components/Terminal.tsx'),
    'utf-8'
  )

  it('keeps the xterm container div outside any view-gated conditional render', () => {
    const conditionallyMounted =
      /\{\s*view\s*(===|!==)\s*['"](term|conv)['"]\s*&&[^]*?ref=\{containerRef\}/.test(
        terminalSource
      )
    expect(conditionallyMounted).toBe(false)
  })

  it('hides the terminal-container div with a class instead of unmounting it', () => {
    const hiddenViaClassName =
      /data-testid="terminal-container"[^]*?className=\{`[^`]*view\s*===\s*'conv'\s*\?\s*'hidden'/.test(
        terminalSource
      )
    expect(hiddenViaClassName).toBe(true)
  })
})
