/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { ToolGroup } from './ConversationItem'
import type { ToolItem } from '../../hooks/useConversationSocket'

vi.mock('../../hooks/useTheme', () => ({ useTheme: () => ({ theme: 'dark' }) }))

afterEach(cleanup)

const tool = (id: string, name: string, extra: Partial<ToolItem> = {}): ToolItem => ({
  id,
  type: 'tool_call',
  tool_name: name,
  tool_summary: `${name.toLowerCase()} something`,
  result: { status: 'ok' },
  ...extra,
})

const run = [tool('1', 'Bash'), tool('2', 'Bash'), tool('3', 'Read')]

describe('ToolGroup', () => {
  it('folds a run into one line that says what happened', () => {
    render(<ToolGroup items={run} isLatest={false} />)

    expect(screen.getByTestId('tool-group-toggle').textContent).toContain('2 commands, 1 file read')
    expect(screen.queryByText('bash something')).toBeNull()
  })

  it('opens on click and shows every call in the run', () => {
    render(<ToolGroup items={run} isLatest={false} />)

    fireEvent.click(screen.getByTestId('tool-group-toggle'))

    expect(screen.getAllByText('bash something')).toHaveLength(2)
    expect(screen.getByText('read something')).toBeTruthy()
  })

  it('starts open while it is the run the agent is still working through', () => {
    render(<ToolGroup items={run} isLatest />)

    expect(screen.getByText('read something')).toBeTruthy()
  })

  it('lets you close the live run and keeps it closed', () => {
    render(<ToolGroup items={run} isLatest />)

    fireEvent.click(screen.getByTestId('tool-group-toggle'))

    expect(screen.queryByText('read something')).toBeNull()
  })

  it('shows a failure on the folded line, where it cannot be missed', () => {
    const failed = [tool('1', 'Bash'), tool('2', 'Bash', { result: { status: 'error' } })]
    render(<ToolGroup items={failed} isLatest={false} />)

    const toggle = screen.getByTestId('tool-group-toggle')
    expect(toggle.textContent).toContain('✗')
    expect(toggle.querySelector('.text-danger')).toBeTruthy()
  })

  it('shows work still in flight', () => {
    const pending = [tool('1', 'Bash'), tool('2', 'Bash', { result: undefined })]
    render(<ToolGroup items={pending} isLatest={false} />)

    expect(screen.getByTestId('tool-group-toggle').textContent).toContain('…')
  })
})
