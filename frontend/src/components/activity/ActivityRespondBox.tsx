import { useState } from 'react'
import { getApiBase } from '../../config'

export default function ActivityRespondBox({ sessionName }: { sessionName: string }) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)

  const send = async () => {
    const value = text.trim()
    if (!value || sending) return
    setSending(true)
    try {
      await fetch(`${getApiBase()}/session/${encodeURIComponent(sessionName)}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: value, send_enter: true }),
      })
      setText('')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex gap-2 border-t border-border-default bg-bg-surface p-2">
      <textarea
        className="flex-1 resize-none rounded bg-input-bg p-2 text-sm text-text-primary"
        rows={1}
        value={text}
        placeholder="Reply to the agent…"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            void send()
          }
        }}
      />
      <button
        className="rounded bg-action px-3 text-sm font-medium text-white disabled:opacity-50"
        disabled={sending || !text.trim()}
        onClick={() => void send()}
      >
        Send
      </button>
    </div>
  )
}
