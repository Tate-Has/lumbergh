import { useState, type KeyboardEvent, type ReactNode } from 'react'
import MarkdownPreview from '@uiw/react-markdown-preview'
import { useTheme } from '../../hooks/useTheme'
import type { ActivityItem } from '../../hooks/useCombinedActivitySocket'
import type { PairedActivityItem } from './pairToolEvents'

// Per-event-type card renderers shared by the combined activity feed.
// Adapted from upstream's ActivityFeed.tsx (single-session view) — same
// visual language (terminal-style Bash block, colored Edit/Write diff,
// ephemeral thinking, collapsed status chips) but reworked for a feed that
// interleaves multiple sessions: every card takes an optional `sessionTag`
// rendered inline in its header row instead of upstream's single-session
// implicit context.
//
// Note: this fork's `ActivityItem` (useCombinedActivitySocket.ts) is a flat,
// unpaired event stream — the hook never pairs tool_call/tool_result itself
// (see that file's docstring). `CombinedActivityFeed.tsx` runs every item
// through `pairToolEvents.ts` before it reaches these cards, merging each
// `tool_result` into its originating `tool_call` (by `session` +
// `tool_use_id`). A `tool_call` card below renders pending ("…") until that
// merge lands a `status`; an unmatched `tool_result` still falls through to
// `ToolResultChip` as a standalone chip.

const TOOL_ICONS: Record<string, string> = {
  Read: '📖',
  Edit: '✏️',
  Write: '✏️',
  Bash: '⚡',
  Grep: '🔍',
  Glob: '🔍',
  Task: '🤖',
}

function parseToolInput(detail?: string | null): Record<string, unknown> {
  if (!detail) return {}
  try {
    const parsed = JSON.parse(detail)
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

const cardShell =
  'block w-full overflow-hidden rounded-[var(--radius-md)] border border-border-default bg-bg-elevated text-left'

/** Props for a card's clickable outer shell — a `<div role="button">`, not a
 *  real `<button>`, since the header row nests its own interactive
 *  `SessionTag` toggle button and a `<button>` cannot contain a `<button>`
 *  (invalid HTML, breaks hydration). `SessionTag` stops propagation on its
 *  own click, so this still only expands/collapses on clicks outside it. */
function expandableShellProps(open: boolean, onToggle: () => void) {
  return {
    role: 'button' as const,
    tabIndex: 0,
    'aria-expanded': open,
    onClick: onToggle,
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onToggle()
      }
    },
  }
}

/** Shared header row: icon, title content, optional sessionTag, status mark. */
function CardHeader({
  icon,
  children,
  sessionTag,
  statusMark,
}: {
  icon?: ReactNode
  children: ReactNode
  sessionTag?: ReactNode
  statusMark?: ReactNode
}) {
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 text-sm">
      {icon}
      <div className="min-w-0 flex-1 flex items-center gap-2">{children}</div>
      {sessionTag}
      {statusMark !== undefined && <span className="shrink-0 text-xs">{statusMark}</span>}
    </div>
  )
}

function BashCard({ item, sessionTag }: { item: PairedActivityItem; sessionTag?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const command = item.tool_summary ?? ''
  const failed = item.status === 'error'
  const hasResult = item.status != null
  return (
    <div
      {...expandableShellProps(open, () => setOpen((v) => !v))}
      className={`${cardShell} cursor-pointer`}
    >
      <CardHeader
        sessionTag={sessionTag}
        statusMark={
          <span className={failed ? 'text-danger' : 'text-text-tertiary'}>
            {hasResult ? (failed ? '❌' : '✓') : '…'}
          </span>
        }
      >
        <span className="select-none font-mono text-xs text-text-muted">$</span>
        <span className="truncate font-mono text-xs text-text-primary">{command}</span>
      </CardHeader>
      {open && (
        <div className="border-t border-border-default bg-bg-sunken px-2 py-1.5">
          <pre className="whitespace-pre-wrap font-mono text-xs text-text-secondary">
            <span className="select-none text-text-muted">$ </span>
            {command}
          </pre>
          {item.resultText && (
            <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap font-mono text-xs text-text-tertiary">
              {item.resultText}
            </pre>
          )}
        </div>
      )}
    </div>
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

function EditCard({ item, sessionTag }: { item: PairedActivityItem; sessionTag?: ReactNode }) {
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
  const failed = item.status === 'error'
  const hasResult = item.status != null
  return (
    <div
      {...expandableShellProps(open, () => setOpen((v) => !v))}
      className={`${cardShell} cursor-pointer`}
    >
      <CardHeader
        icon={<span>✏️</span>}
        sessionTag={sessionTag}
        statusMark={hasResult ? (failed ? '❌' : '✓') : '…'}
      >
        <span className="truncate font-mono text-xs text-text-primary" title={filePath}>
          {filePath}
        </span>
      </CardHeader>
      {open && (removed || added) && (
        <div className="max-h-72 overflow-auto border-t border-border-default bg-bg-sunken py-1 font-mono text-xs leading-relaxed">
          {removed && <DiffLines text={removed} sign="-" />}
          {added && <DiffLines text={added} sign="+" />}
        </div>
      )}
    </div>
  )
}

function GenericToolCard({
  item,
  sessionTag,
}: {
  item: PairedActivityItem
  sessionTag?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const icon = TOOL_ICONS[item.tool_name ?? ''] ?? '🔧'
  const failed = item.status === 'error'
  const hasResult = item.status != null
  return (
    <div
      {...expandableShellProps(open, () => setOpen((v) => !v))}
      className={`${cardShell} cursor-pointer p-2 text-sm`}
    >
      <div className="flex items-center gap-2">
        <span>{icon}</span>
        <span className="font-medium text-text-primary">{item.tool_name}</span>
        <span className="truncate text-text-tertiary">{item.tool_summary}</span>
        {sessionTag}
        <span className="ml-auto shrink-0 text-xs">{hasResult ? (failed ? '❌' : '✓') : '…'}</span>
      </div>
      {open && (item.tool_detail || item.resultText) && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-text-tertiary">
          {item.tool_detail}
          {item.resultText ? `\n\n— output —\n${item.resultText}` : ''}
        </pre>
      )}
    </div>
  )
}

/** Dispatches a `tool_call` item to the Bash/Edit-Write/generic renderer. */
export function ToolCallCard({
  item,
  sessionTag,
}: {
  item: PairedActivityItem
  sessionTag?: ReactNode
}) {
  if (item.tool_name === 'Bash') return <BashCard item={item} sessionTag={sessionTag} />
  if (item.tool_name === 'Edit' || item.tool_name === 'Write' || item.tool_name === 'NotebookEdit')
    return <EditCard item={item} sessionTag={sessionTag} />
  return <GenericToolCard item={item} sessionTag={sessionTag} />
}

/** `thinking` block — collapsed by default, only ever rendered while it's the
 *  latest event for its session (caller filters, matching upstream's
 *  ephemeral-thinking behavior). */
export function ThinkingCard({ item, sessionTag }: { item: ActivityItem; sessionTag?: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`${cardShell} px-2 py-1.5 text-sm`}>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="text-text-tertiary italic cursor-pointer"
        >
          {open ? '▾ thinking' : '▸ thinking'}
        </button>
        {sessionTag}
      </div>
      {open && (
        <div className="mt-1 border-l-2 border-border-default pl-2 text-text-tertiary">
          {item.text}
        </div>
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

/** `user_message` / `agent_message` — plain message bubble. */
export function MessageCard({ item, sessionTag }: { item: ActivityItem; sessionTag?: ReactNode }) {
  const isUser = item.type === 'user_message'
  return (
    <div
      className={`${cardShell} p-2 ${isUser ? 'ml-auto max-w-[85%] bg-action/10' : 'max-w-[95%]'}`}
    >
      <div className="mb-1 flex items-center gap-2">{sessionTag}</div>
      {isUser ? (
        <div className="text-sm text-text-primary whitespace-pre-wrap">{item.text}</div>
      ) : (
        <AgentMarkdown text={item.text ?? ''} />
      )}
    </div>
  )
}

/** Harness noise / `status` — collapsed to a single-line chip. */
export function StatusChip({ item, sessionTag }: { item: ActivityItem; sessionTag?: ReactNode }) {
  return (
    <div className="flex items-center justify-center gap-2 text-xs text-text-muted">
      {sessionTag}
      <span>{item.text}</span>
    </div>
  )
}

/** `tool_result` events that never got paired with their originating
 *  `tool_call` in this interleaved stream (see file-level note above) — shown
 *  as a minimal one-line chip rather than dropped silently. */
export function ToolResultChip({
  item,
  sessionTag,
}: {
  item: ActivityItem
  sessionTag?: ReactNode
}) {
  const failed = item.status === 'error'
  return (
    <div className="flex items-center gap-2 text-xs text-text-muted">
      {sessionTag}
      <span className={failed ? 'text-danger' : 'text-text-tertiary'}>{failed ? '❌' : '✓'}</span>
      <span className="truncate">{item.tool_summary || item.text || 'tool result'}</span>
    </div>
  )
}

/** Dispatches any ActivityItem to its card renderer. */
export function ActivityCard({
  item,
  sessionTag,
}: {
  item: PairedActivityItem
  sessionTag?: ReactNode
}) {
  switch (item.type) {
    case 'user_message':
    case 'agent_message':
      return <MessageCard item={item} sessionTag={sessionTag} />
    case 'thinking':
      return <ThinkingCard item={item} sessionTag={sessionTag} />
    case 'tool_call':
      return <ToolCallCard item={item} sessionTag={sessionTag} />
    case 'tool_result':
      return <ToolResultChip item={item} sessionTag={sessionTag} />
    case 'status':
      return <StatusChip item={item} sessionTag={sessionTag} />
    default:
      return null
  }
}
