/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { Item } from './ConversationItem'
import type { ToolItem } from '../../hooks/useConversationSocket'

vi.mock('../../hooks/useTheme', () => ({ useTheme: () => ({ theme: 'dark' }) }))

const detail = JSON.stringify({
  questions: [
    {
      question: 'Push to dev now?',
      header: 'Push batch',
      multiSelect: false,
      options: [
        { label: 'Push — build & deploy', description: 'Fires CI.' },
        { label: "Hold — don't push yet", description: 'No CI fires.' },
      ],
    },
  ],
})

const ask = (extra: Partial<ToolItem> = {}): ToolItem => ({
  id: 'q1',
  type: 'tool_call',
  tool_name: 'AskUserQuestion',
  tool_detail: detail,
  ...extra,
})

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue({ ok: true })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('a question the agent is waiting on', () => {
  it('shows the question and every option without anyone opening a card', () => {
    render(<Item item={ask()} sessionName="mysession" />)

    expect(screen.getByText('Push to dev now?')).toBeTruthy()
    expect(screen.getByText('Push — build & deploy')).toBeTruthy()
    expect(screen.getByText("Hold — don't push yet")).toBeTruthy()
    expect(screen.getByText('Fires CI.')).toBeTruthy()
  })

  it('answers it by moving the picker to that option and confirming', async () => {
    render(<Item item={ask()} sessionName="mysession" />)

    fireEvent.click(screen.getByRole('button', { name: /Hold/ }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/session/mysession/select-option')
    expect(JSON.parse(init.body)).toEqual({ index: 1 })
  })

  it('cannot be answered from here once it already has an answer', () => {
    render(
      <Item
        item={ask({
          result: {
            status: 'ok',
            text: 'Your questions have been answered: "Push to dev now?"="Push — build & deploy".',
          },
        })}
        sessionName="mysession"
      />
    )

    expect(screen.queryByRole('button', { name: /Hold/ })).toBeNull()
    expect(screen.getByTestId('question-answer').textContent).toContain('Push — build & deploy')
  })
})
