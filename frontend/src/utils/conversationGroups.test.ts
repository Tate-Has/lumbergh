import { describe, it, expect } from 'vitest'
import { groupToolRuns, summarizeRun, runStatus, type ConversationRow } from './conversationGroups'
import type { RenderItem, ToolItem } from '../hooks/useConversationSocket'

const say = (id: string, text = 'hello'): RenderItem => ({ id, type: 'agent_message', text })

const tool = (id: string, tool_name: string, extra: Partial<ToolItem> = {}): ToolItem => ({
  id,
  type: 'tool_call',
  tool_name,
  tool_summary: `${tool_name} thing`,
  result: { status: 'ok' },
  ...extra,
})

const shape = (rows: ConversationRow[]) =>
  rows.map((r) => (r.kind === 'group' ? `group(${r.items.length})` : r.item.id))

describe('groupToolRuns', () => {
  it('leaves prose and lone tool calls alone', () => {
    const rows = groupToolRuns([say('a'), tool('t1', 'Bash'), say('b')])

    expect(shape(rows)).toEqual(['a', 't1', 'b'])
  })

  it('folds two or more adjacent tool calls into one row', () => {
    const rows = groupToolRuns([say('a'), tool('t1', 'Bash'), tool('t2', 'Read'), say('b')])

    expect(shape(rows)).toEqual(['a', 'group(2)', 'b'])
  })

  it('never folds a question away inside a run of tool calls', () => {
    const rows = groupToolRuns([
      tool('t1', 'Bash'),
      tool('q1', 'AskUserQuestion'),
      tool('t2', 'Bash'),
    ])

    expect(shape(rows)).toEqual(['t1', 'q1', 't2'])
  })

  it('groups a run that opens or closes the feed', () => {
    const rows = groupToolRuns([
      tool('t1', 'Bash'),
      tool('t2', 'Bash'),
      say('a'),
      tool('t3', 'Read'),
      tool('t4', 'Read'),
    ])

    expect(shape(rows)).toEqual(['group(2)', 'a', 'group(2)'])
  })

  it('keeps a run together across different tools', () => {
    const rows = groupToolRuns([tool('t1', 'Read'), tool('t2', 'Edit'), tool('t3', 'Bash')])

    expect(shape(rows)).toEqual(['group(3)'])
  })

  it('takes its key from the first item, so the row survives a re-render', () => {
    const rows = groupToolRuns([tool('t1', 'Bash'), tool('t2', 'Bash')])

    expect(rows[0].key).toBe('t1')
  })

  it('marks only the run that ends the feed as the live one', () => {
    const rows = groupToolRuns([
      tool('t1', 'Bash'),
      tool('t2', 'Bash'),
      say('a'),
      tool('t3', 'Bash'),
      tool('t4', 'Bash'),
    ])

    expect(rows[0].kind === 'group' && rows[0].isLatest).toBe(false)
    expect(rows[2].kind === 'group' && rows[2].isLatest).toBe(true)
  })

  it('survives an empty feed', () => {
    expect(groupToolRuns([])).toEqual([])
  })
})

describe('summarizeRun', () => {
  it('counts by what the tools did, not by their names', () => {
    expect(summarizeRun([tool('1', 'Bash'), tool('2', 'Bash'), tool('3', 'Read')])).toBe(
      '2 commands, 1 file read'
    )
  })

  it('says edits, reads and searches in plain words', () => {
    expect(summarizeRun([tool('1', 'Edit'), tool('2', 'Write')])).toBe('2 edits')
    expect(summarizeRun([tool('1', 'Grep'), tool('2', 'Glob')])).toBe('2 searches')
  })

  it('singularises', () => {
    expect(summarizeRun([tool('1', 'Bash'), tool('2', 'Read')])).toBe('1 command, 1 file read')
  })

  it('falls back to a plain count for tools it has no word for', () => {
    expect(summarizeRun([tool('1', 'WebFetch'), tool('2', 'Task')])).toBe('2 tool calls')
  })
})

describe('runStatus', () => {
  it('is done when every call came back clean', () => {
    expect(runStatus([tool('1', 'Bash'), tool('2', 'Read')])).toBe('ok')
  })

  it('is still running while any call has no result', () => {
    expect(runStatus([tool('1', 'Bash'), tool('2', 'Read', { result: undefined })])).toBe('running')
  })

  it('reports a failure even when it is buried among successes', () => {
    const failed = tool('2', 'Bash', { result: { status: 'error' } })

    expect(runStatus([tool('1', 'Bash'), failed, tool('3', 'Read')])).toBe('error')
  })

  it('lets a failure outrank a call still in flight', () => {
    const failed = tool('1', 'Bash', { result: { status: 'error' } })

    expect(runStatus([failed, tool('2', 'Read', { result: undefined })])).toBe('error')
  })
})
