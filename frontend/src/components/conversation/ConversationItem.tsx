import { useState } from 'react'
import MarkdownPreview from '@uiw/react-markdown-preview'
import { type RenderItem, type ToolItem } from '../../hooks/useConversationSocket'
import { runStatus, summarizeRun, type RunStatus } from '../../utils/conversationGroups'
import { useTheme } from '../../hooks/useTheme'
import QuestionCard from './QuestionCard'
import { ASK_QUESTION_TOOL } from '../../utils/askUserQuestion'

const TOOL_ICONS: Record<string, string> = {
  Read: '📖',
  Edit: '✏️',
  Write: '✏️',
  Bash: '⚡',
  Grep: '🔍',
  Glob: '🔍',
  Task: '🤖',
}

function parseToolInput(detail?: string): Record<string, unknown> {
  if (!detail) return {}
  try {
    const parsed = JSON.parse(detail)
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

function statusMark(item: ToolItem): string {
  if (!item.result) return '…'
  return item.result.status === 'error' ? '❌' : '✓'
}

/** Tool calls are what the agent did, not what it said. They sit unboxed and dim
 * beside the prose, and only earn a surface once you open one.
 *
 * Inside an opened run they read one step brighter: you unfolded it to read the
 * commands, and marginalia dim enough to skip past is too dim to actually read.
 */
const cardShell =
  'block w-full overflow-hidden rounded text-left transition-colors hover:text-text-secondary'

function shellFor(inGroup?: boolean) {
  return `${cardShell} ${inGroup ? 'text-text-tertiary' : 'text-text-muted'}`
}

function BashCard({ item, inGroup }: { item: ToolItem; inGroup?: boolean }) {
  const [open, setOpen] = useState(false)
  const failed = item.result?.status === 'error'
  const command = item.tool_summary ?? ''
  return (
    <button onClick={() => setOpen((v) => !v)} className={shellFor(inGroup)}>
      <div className="flex items-center gap-2 px-2 py-0.5 font-mono text-xs">
        <span className="select-none opacity-60">$</span>
        <span className="truncate">{command}</span>
        <span className={`ml-auto ${failed ? 'text-danger' : 'opacity-60'}`}>
          {item.result ? (failed ? '✗' : '✓') : '…'}
        </span>
      </div>
      {open && (
        <div className="mt-0.5 rounded border border-border-default bg-bg-sunken px-2 py-1.5">
          <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
            <span className="select-none text-text-muted">$ </span>
            {command}
          </pre>
          {item.result?.text && (
            <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap font-mono text-xs text-text-tertiary">
              {item.result.text}
            </pre>
          )}
        </div>
      )}
    </button>
  )
}

function DiffLines({ text, sign }: { text: string; sign: '+' | '-' }) {
  const tone = sign === '+' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'
  return (
    <div className={tone}>
      {text.split('\n').map((line, i) => (
        <div key={i} className="whitespace-pre-wrap px-2">
          <span className="select-none opacity-60">{sign} </span>
          {line || ' '}
        </div>
      ))}
    </div>
  )
}

function EditCard({ item, inGroup }: { item: ToolItem; inGroup?: boolean }) {
  const [open, setOpen] = useState(false)
  const input = parseToolInput(item.tool_detail)
  // tool_summary is the project-relativized path from the backend; prefer it.
  const filePath = item.tool_summary || String(input.file_path ?? '')
  const removed = typeof input.old_string === 'string' ? input.old_string : ''
  const added =
    typeof input.new_string === 'string'
      ? input.new_string
      : typeof input.content === 'string'
        ? input.content
        : ''
  return (
    <button onClick={() => setOpen((v) => !v)} className={shellFor(inGroup)}>
      <div className="flex items-center gap-2 px-2 py-0.5 font-mono text-xs">
        <span className="select-none opacity-60">✏</span>
        <span className="truncate" title={filePath}>
          {filePath}
        </span>
        <span className="ml-auto opacity-60">{statusMark(item)}</span>
      </div>
      {open && (removed || added) && (
        <div className="mt-0.5 max-h-72 overflow-auto rounded border border-border-default bg-bg-sunken py-1 font-mono text-xs leading-relaxed">
          {removed && <DiffLines text={removed} sign="-" />}
          {added && <DiffLines text={added} sign="+" />}
        </div>
      )}
    </button>
  )
}

function GenericToolCard({ item, inGroup }: { item: ToolItem; inGroup?: boolean }) {
  const [open, setOpen] = useState(false)
  const icon = TOOL_ICONS[item.tool_name ?? ''] ?? '🔧'
  return (
    <button onClick={() => setOpen((v) => !v)} className={shellFor(inGroup)}>
      <div className="flex items-center gap-2 px-2 py-0.5 font-mono text-xs">
        <span className="select-none opacity-60">{icon}</span>
        <span className="shrink-0">{item.tool_name}</span>
        <span className="truncate opacity-80">{item.tool_summary}</span>
        <span className="ml-auto opacity-60">{statusMark(item)}</span>
      </div>
      {open && (
        <pre className="mt-0.5 overflow-x-auto whitespace-pre-wrap rounded border border-border-default bg-bg-sunken p-2 text-xs text-text-tertiary">
          {item.tool_detail}
          {item.result?.text ? `\n\n— output —\n${item.result.text}` : ''}
        </pre>
      )}
    </button>
  )
}

function ToolCard({ item, inGroup }: { item: ToolItem; inGroup?: boolean }) {
  if (item.tool_name === 'Bash') return <BashCard item={item} inGroup={inGroup} />
  if (item.tool_name === 'Edit' || item.tool_name === 'Write' || item.tool_name === 'NotebookEdit')
    return <EditCard item={item} inGroup={inGroup} />
  return <GenericToolCard item={item} inGroup={inGroup} />
}

const RUN_MARK: Record<RunStatus, string> = { ok: '✓', error: '✗', running: '…' }

/** A run of tool calls, folded into one line.
 *
 * `isLatest` opens the run the agent is still working through, so watching a
 * session live still shows the play-by-play; it folds itself once the agent says
 * something after it. A run you have opened or closed by hand keeps whatever you
 * chose — the default only applies until you touch it.
 */
export function ToolGroup({ items, isLatest }: { items: ToolItem[]; isLatest: boolean }) {
  const [choice, setChoice] = useState<boolean | null>(null)
  const open = choice ?? isLatest
  const status = runStatus(items)

  return (
    <div className="text-text-muted">
      <button
        onClick={() => setChoice(!open)}
        className="flex w-full items-center gap-2 rounded px-2 py-0.5 text-left text-xs hover:text-text-secondary"
        data-testid="tool-group-toggle"
      >
        <span className="select-none opacity-60">{open ? '⌄' : '›'}</span>
        <span>{summarizeRun(items)}</span>
        <span className={`ml-auto ${status === 'error' ? 'text-danger' : 'opacity-60'}`}>
          {RUN_MARK[status]}
        </span>
      </button>
      {open && (
        <div className="ml-3 border-l border-border-default pl-1">
          {items.map((item) => (
            <ToolCard key={item.id} item={item} inGroup />
          ))}
        </div>
      )}
    </div>
  )
}

function ThinkingBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="text-sm">
      <button onClick={() => setOpen((v) => !v)} className="text-text-tertiary italic">
        {open ? '▾ thinking' : '▸ thinking'}
      </button>
      {open && (
        <div className="mt-1 border-l-2 border-border-default pl-2 text-text-tertiary">{text}</div>
      )}
    </div>
  )
}

function AgentMarkdown({ text }: { text: string }) {
  const { theme } = useTheme()
  return (
    <div
      data-color-mode={theme === 'dark' ? 'dark' : 'light'}
      className="conversation-prose text-base leading-relaxed"
    >
      <MarkdownPreview source={text} style={{ background: 'transparent' }} />
    </div>
  )
}

export function Item({ item, sessionName }: { item: RenderItem; sessionName: string }) {
  if (item.type === 'user_message')
    return (
      <div className="ml-auto max-w-[85%] rounded-lg bg-action/20 p-2 text-sm text-text-primary">
        {item.text}
      </div>
    )
  if (item.type === 'agent_message')
    return (
      <div className="text-text-primary">
        <AgentMarkdown text={item.text ?? ''} />
      </div>
    )
  if (item.type === 'thinking') return <ThinkingBlock text={item.text ?? ''} />
  if (item.type === 'tool_call') {
    if (item.tool_name === ASK_QUESTION_TOOL)
      return <QuestionCard item={item as ToolItem} sessionName={sessionName} />
    return <ToolCard item={item as ToolItem} />
  }
  if (item.type === 'status')
    return <div className="text-center text-xs text-text-muted">{item.text}</div>
  return null
}
