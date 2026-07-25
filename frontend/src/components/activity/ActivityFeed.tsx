import { useEffect, useRef, useState } from 'react'
import MarkdownPreview from '@uiw/react-markdown-preview'
import { useActivitySocket, type RenderItem, type ToolItem } from '../../hooks/useActivitySocket'
import { useTheme } from '../../hooks/useTheme'
import ActivityRespondBox from './ActivityRespondBox'

const TOOL_ICONS: Record<string, string> = {
  Read: '📖',
  Edit: '✏️',
  Write: '✏️',
  Bash: '⚡',
  Grep: '🔍',
  Glob: '🔍',
  Task: '🤖',
}

function ToolCard({ item }: { item: ToolItem }) {
  const [open, setOpen] = useState(false)
  const icon = TOOL_ICONS[item.tool_name ?? ''] ?? '🔧'
  const failed = item.result?.status === 'error'
  return (
    <button
      onClick={() => setOpen((v) => !v)}
      className="w-full rounded border border-neutral-800 bg-neutral-900/60 p-2 text-left text-sm"
    >
      <div className="flex items-center gap-2">
        <span>{icon}</span>
        <span className="font-medium text-neutral-200">{item.tool_name}</span>
        <span className="truncate text-neutral-400">{item.tool_summary}</span>
        <span className="ml-auto text-xs">{item.result ? (failed ? '❌' : '✓') : '…'}</span>
      </div>
      {open && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-neutral-400">
          {item.tool_detail}
          {item.result?.text ? `\n\n— output —\n${item.result.text}` : ''}
        </pre>
      )}
    </button>
  )
}

function ThinkingBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="text-sm">
      <button onClick={() => setOpen((v) => !v)} className="text-neutral-500 italic">
        {open ? '▾ thinking' : '▸ thinking'}
      </button>
      {open && (
        <div className="mt-1 border-l-2 border-neutral-700 pl-2 text-neutral-400">{text}</div>
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

function Item({ item }: { item: RenderItem }) {
  if (item.type === 'user_message')
    return (
      <div className="ml-auto max-w-[85%] rounded-lg bg-blue-600/20 p-2 text-sm text-neutral-100">
        {item.text}
      </div>
    )
  if (item.type === 'agent_message')
    return (
      <div className="max-w-[95%] text-neutral-100">
        <AgentMarkdown text={item.text ?? ''} />
      </div>
    )
  if (item.type === 'thinking') return <ThinkingBlock text={item.text ?? ''} />
  if (item.type === 'tool_call') return <ToolCard item={item as ToolItem} />
  if (item.type === 'status')
    return <div className="text-center text-xs text-neutral-600">{item.text}</div>
  return null
}

export default function ActivityFeed({ sessionName }: { sessionName: string }) {
  const { items, noTranscript } = useActivitySocket({ sessionName })
  const scrollRef = useRef<HTMLDivElement>(null)
  const [following, setFollowing] = useState(true)

  useEffect(() => {
    if (following && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [items, following])

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    setFollowing(atBottom)
  }

  if (noTranscript) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-sm text-neutral-500">
        No transcript found for this session yet. Start interacting in the terminal.
      </div>
    )
  }

  return (
    <div className="relative flex h-full flex-col">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 space-y-3 overflow-y-auto overscroll-contain p-3"
      >
        {items.map((item) => (
          <Item key={item.id} item={item} />
        ))}
      </div>
      {!following && (
        <button
          onClick={() => setFollowing(true)}
          className="absolute bottom-16 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-3 py-1 text-xs text-white shadow"
        >
          Jump to latest ↓
        </button>
      )}
      <ActivityRespondBox sessionName={sessionName} />
    </div>
  )
}
