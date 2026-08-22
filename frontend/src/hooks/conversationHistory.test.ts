import { describe, it, expect } from 'vitest'
import { applyHistory, applyOlderHistory, mergeEvents } from './useConversationSocket'
import type { ActivityEvent, RenderItem } from './useConversationSocket'

const msg = (id: string): ActivityEvent => ({ type: 'agent_message', id, text: `line ${id}` })
const call = (id: string, useId: string): ActivityEvent => ({
  type: 'tool_call',
  id,
  tool_use_id: useId,
  tool_name: 'Bash',
})

describe('applyHistory', () => {
  it('replaces whatever was there with the page, in one go', () => {
    const items = applyHistory([msg('stale')] as RenderItem[], [msg('1'), msg('2')])

    expect(items.map((i) => i.id)).toEqual(['1', '2'])
  })

  it('folds tool results into their calls, like the live path does', () => {
    const items = applyHistory(
      [],
      [
        call('c1', 'use-1'),
        { type: 'tool_result', id: 'r1', tool_use_id: 'use-1', status: 'ok', text: 'done' },
      ]
    )

    expect(items).toHaveLength(1)
    expect(items[0].type).toBe('tool_call')
    expect((items[0] as { result?: { text?: string } }).result?.text).toBe('done')
  })
})

describe('applyOlderHistory', () => {
  it('puts the older page in front of what is already shown', () => {
    const items = applyOlderHistory([msg('3'), msg('4')] as RenderItem[], [msg('1'), msg('2')])

    expect(items.map((i) => i.id)).toEqual(['1', '2', '3', '4'])
  })

  it('resolves a result that belongs to a call in the older page', () => {
    const shown = applyHistory(
      [],
      [{ type: 'tool_result', id: 'r1', tool_use_id: 'use-1', status: 'ok', text: 'late' }]
    )
    const items = applyOlderHistory(shown, [call('c1', 'use-1')])

    const toolCall = items.find((i) => i.type === 'tool_call')
    expect((toolCall as { result?: { text?: string } })?.result?.text).toBe('late')
  })

  it('changes nothing when there is no older page', () => {
    const shown = [msg('1')] as RenderItem[]

    expect(applyOlderHistory(shown, [])).toEqual(shown)
  })
})

describe('mergeEvents still handles the live stream', () => {
  it('appends a new event', () => {
    expect(mergeEvents([msg('1')] as RenderItem[], msg('2')).map((i) => i.id)).toEqual(['1', '2'])
  })
})
