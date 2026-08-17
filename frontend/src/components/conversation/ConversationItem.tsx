import { useState } from 'react'
import MarkdownPreview from '@uiw/react-markdown-preview'
import { type RenderItem, type ToolItem } from '../../hooks/useConversationSocket'
import { useTheme } from '../../hooks/useTheme'

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

const cardShell =
  'block w-full overflow-hidden rounded border border-border-default bg-bg-surface text-left'

function BashCard({ item }: { item: ToolItem }) {
  const [open, setOpen] = useState(false)
  const failed = item.result?.status === 'error'
  const command = item.tool_summary ?? ''
  return (
    <button onClick={() => setOpen((v) => !v)} className={cardShell}>
      <div className="flex items-center gap-2 px-2 py-1.5 font-mono text-xs">
        <span className="select-none text-text-muted">$</span>
        <span className="truncate text-text-primary">{command}</span>
        <span className={`ml-auto ${failed ? 'text-danger' : 'text-text-tertiary'}`}>
          {item.result ? (failed ? '✗' : '✓') : '…'}
        </span>
      </div>
      {open && (
        <div className="border-t border-border-default bg-bg-sunken px-2 py-1.5">
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

function EditCard({ item }: { item: ToolItem }) {
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
    <button onClick={() => setOpen((v) => !v)} className={cardShell}>
      <div className="flex items-center gap-2 px-2 py-1.5 text-sm">
        <span>✏️</span>
        <span className="truncate font-mono text-xs text-text-primary" title={filePath}>
          {filePath}
        </span>
        <span className="ml-auto text-xs">{statusMark(item)}</span>
      </div>
      {open && (removed || added) && (
        <div className="max-h-72 overflow-auto border-t border-border-default bg-bg-sunken py-1 font-mono text-xs leading-relaxed">
          {removed && <DiffLines text={removed} sign="-" />}
          {added && <DiffLines text={added} sign="+" />}
        </div>
      )}
    </button>
  )
}

function GenericToolCard({ item }: { item: ToolItem }) {
  const [open, setOpen] = useState(false)
  const icon = TOOL_ICONS[item.tool_name ?? ''] ?? '🔧'
  return (
    <button onClick={() => setOpen((v) => !v)} className={`${cardShell} p-2 text-sm`}>
      <div className="flex items-center gap-2">
        <span>{icon}</span>
        <span className="font-medium text-text-primary">{item.tool_name}</span>
        <span className="truncate text-text-tertiary">{item.tool_summary}</span>
        <span className="ml-auto text-xs">{statusMark(item)}</span>
      </div>
      {open && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-text-tertiary">
          {item.tool_detail}
          {item.result?.text ? `\n\n— output —\n${item.result.text}` : ''}
        </pre>
      )}
    </button>
  )
}

function ToolCard({ item }: { item: ToolItem }) {
  if (item.tool_name === 'Bash') return <BashCard item={item} />
  if (item.tool_name === 'Edit' || item.tool_name === 'Write' || item.tool_name === 'NotebookEdit')
    return <EditCard item={item} />
  return <GenericToolCard item={item} />
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
    <div data-color-mode={theme === 'dark' ? 'dark' : 'light'} className="text-sm">
      <MarkdownPreview source={text} style={{ background: 'transparent' }} />
    </div>
  )
}

export function Item({ item }: { item: RenderItem }) {
  if (item.type === 'user_message')
    return (
      <div className="ml-auto max-w-[85%] rounded-lg bg-action/20 p-2 text-sm text-text-primary">
        {item.text}
      </div>
    )
  if (item.type === 'agent_message')
    return (
      <div className="max-w-[95%] text-text-primary">
        <AgentMarkdown text={item.text ?? ''} />
      </div>
    )
  if (item.type === 'thinking') return <ThinkingBlock text={item.text ?? ''} />
  if (item.type === 'tool_call') return <ToolCard item={item as ToolItem} />
  if (item.type === 'status')
    return <div className="text-center text-xs text-text-muted">{item.text}</div>
  return null
}
