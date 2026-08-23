import type { RenderItem, ToolItem } from '../hooks/useConversationSocket'
import { ASK_QUESTION_TOOL } from './askUserQuestion'

/** One row of the conversation feed: either a single item, or a run of adjacent
 * tool calls folded together.
 *
 * Four boxed tool cards between two sentences bury the sentences. A run is one
 * thing the agent did, so it reads as one row until you ask for the detail.
 */
export type ConversationRow =
  | { kind: 'item'; key: string; item: RenderItem }
  | { kind: 'group'; key: string; items: ToolItem[]; isLatest: boolean }

export type RunStatus = 'ok' | 'error' | 'running'

/** Plain words for what a tool did, so a summary reads like a sentence rather
 * than an inventory of tool names. Tools with no entry fall back to a count. */
const TOOL_NOUNS: Record<string, [singular: string, plural: string]> = {
  Bash: ['command', 'commands'],
  Read: ['file read', 'files read'],
  Edit: ['edit', 'edits'],
  Write: ['edit', 'edits'],
  NotebookEdit: ['edit', 'edits'],
  Grep: ['search', 'searches'],
  Glob: ['search', 'searches'],
}

export function groupToolRuns(items: RenderItem[]): ConversationRow[] {
  const rows: ConversationRow[] = []
  let run: ToolItem[] = []

  const flush = (isLatest: boolean) => {
    if (run.length === 0) return
    rows.push(
      run.length === 1
        ? { kind: 'item', key: run[0].id, item: run[0] }
        : { kind: 'group', key: run[0].id, items: run, isLatest }
    )
    run = []
  }

  for (const item of items) {
    // A question the session is stopped on is not machinery to fold away — it
    // is the one row the reader has to see and act on.
    if (item.type === 'tool_call' && item.tool_name !== ASK_QUESTION_TOOL) {
      run.push(item as ToolItem)
      continue
    }
    flush(false)
    rows.push({ kind: 'item', key: item.id, item })
  }
  // Only a run the feed ends on is "live" — the agent is still working through it.
  flush(true)
  return rows
}

export function summarizeRun(items: ToolItem[]): string {
  const counts = new Map<string, number>()
  let unnamed = 0
  for (const item of items) {
    const noun = TOOL_NOUNS[item.tool_name ?? '']
    if (!noun) {
      unnamed += 1
      continue
    }
    const key = noun[1]
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }

  const parts = [...counts].map(([plural, count]) => {
    const singular = Object.values(TOOL_NOUNS).find((n) => n[1] === plural)?.[0] ?? plural
    return `${count} ${count === 1 ? singular : plural}`
  })
  if (unnamed) parts.push(`${unnamed} tool call${unnamed === 1 ? '' : 's'}`)
  return parts.join(', ')
}

export function runStatus(items: ToolItem[]): RunStatus {
  // A failure outranks work still in flight: it is the one thing a folded run
  // must never hide.
  if (items.some((i) => i.result?.status === 'error')) return 'error'
  if (items.some((i) => !i.result)) return 'running'
  return 'ok'
}
