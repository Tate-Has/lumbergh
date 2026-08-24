/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Item } from './ConversationItem'
import type { RenderItem, ToolItem } from '../../hooks/useConversationSocket'

vi.mock('../../hooks/useTheme', () => ({ useTheme: () => ({ theme: 'dark' }) }))

afterEach(cleanup)

const agentMessage: RenderItem = {
  id: 'a1',
  type: 'agent_message',
  text: 'The pane is as wide as you made it.',
} as RenderItem

const ask: ToolItem = {
  id: 'q1',
  type: 'tool_call',
  tool_name: 'AskUserQuestion',
  tool_detail: JSON.stringify({
    questions: [
      {
        question: 'Push to dev now?',
        header: 'Push batch',
        multiSelect: false,
        options: [{ label: 'Push', description: 'Fires CI.' }],
      },
    ],
  }),
}

describe('conversation width', () => {
  it('lets agent prose use the whole pane', () => {
    const { container } = render(<Item item={agentMessage} sessionName="s" />)

    expect(container.querySelector('[class*="max-w-"]')).toBeNull()
  })

  it('lets a question card use the whole pane', () => {
    render(<Item item={ask as RenderItem} sessionName="s" />)

    expect(screen.getByTestId('question-card').className).not.toContain('max-w-')
  })

  it('keeps your own messages as a bubble that does not span the pane', () => {
    const { container } = render(
      <Item item={{ id: 'u1', type: 'user_message', text: 'hi' } as RenderItem} sessionName="s" />
    )

    expect(container.querySelector('[class*="max-w-"]')).not.toBeNull()
  })
})
