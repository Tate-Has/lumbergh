import { useParams, useNavigate } from 'react-router-dom'
import Terminal from '../components/Terminal'
import { getApiBase } from '../config'
import { useSessionSwitchKeys } from '../hooks/useSessionSwitchKeys'
import { useSessionView } from '../hooks/useSessionView'
import { useConversationScale } from '../hooks/useConversationScale'

export default function TerminalWindow() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  useSessionSwitchKeys(name)
  const { view, toggleView } = useSessionView()
  const { scale, setScale } = useConversationScale()

  if (!name) return null

  const cycleSession = (direction: 'next' | 'prev') => {
    fetch(`${getApiBase()}/sessions`)
      .then((r) => r.json())
      .then((data) => {
        const sessions: { name: string }[] = data.sessions || []
        const idx = sessions.findIndex((s) => s.name === name)
        if (idx === -1 || sessions.length < 2) return
        const nextIdx =
          direction === 'next'
            ? (idx + 1) % sessions.length
            : (idx - 1 + sessions.length) % sessions.length
        navigate(`/session/${sessions[nextIdx].name}/term`, { replace: true })
      })
      .catch(() => {})
  }

  return (
    <div className="fixed inset-0 bg-bg-base">
      <Terminal
        sessionName={name}
        onCycleSession={cycleSession}
        // A session opened straight into Conv attaches its PTY at the cached
        // grid while the terminal is hidden. A container ResizeObserver refits
        // once it is shown, but only Terminal's re-show path also drops the
        // last-sent-size cache, so without this a size another client changed
        // meanwhile is deduped away and never re-asserted to the shared tmux
        // window. This is the same visibility signal SessionDetail passes.
        isVisible={view === 'term'}
        view={view}
        onToggleView={toggleView}
        scale={scale}
        onScaleChange={setScale}
      />
    </div>
  )
}
