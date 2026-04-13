import type { PomodoroState } from '../../types/focus'

interface TopbarProps {
  pomo: PomodoroState
  onPomoPause: () => void
  onPomoResume: () => void
  onPomoStop: () => void
}

function formatRemaining(remaining: number): string {
  return (
    String(Math.floor(remaining / 60)).padStart(2, '0') +
    ':' +
    String(remaining % 60).padStart(2, '0')
  )
}

export default function Topbar({ pomo, onPomoPause, onPomoResume, onPomoStop }: TopbarProps) {
  const showBar = pomo.active

  if (!showBar) return null

  return (
    <div className="topbar flex justify-center items-center px-8 py-2 border-b border-border-subtle shrink-0">
      <div
        className={`topbar-timer flex items-center gap-2 px-3 py-1 rounded-lg bg-orange-subtle border border-accent text-[0.8rem] font-semibold text-text-primary${pomo.phase === 'break' ? ' break' : ''}`}
        id="pomoTimer"
      >
        <span className="pomo-icon text-base">{'\uD83C\uDF45'}</span>
        <span
          className="pomo-task max-w-[160px] overflow-hidden text-ellipsis whitespace-nowrap text-text-secondary font-medium"
          id="pomoTaskTitle"
        >
          {pomo.taskTitle}
        </span>
        <span
          className="pomo-phase text-[0.7rem] uppercase tracking-wide text-text-muted"
          id="pomoPhase"
        >
          {pomo.phase}
        </span>
        <span
          className="pomo-countdown tabular-nums font-bold text-accent min-w-[40px]"
          id="pomoCountdown"
        >
          {formatRemaining(pomo.remaining)}
        </span>
        {pomo.running ? (
          <button
            className="pomo-btn bg-transparent border border-border-default rounded px-1.5 py-0.5 cursor-pointer text-text-secondary transition-all duration-150 hover:border-accent hover:text-accent flex items-center justify-center"
            id="pomoPauseBtn"
            title="Pause"
            onClick={onPomoPause}
          >
            <svg width="10" height="12" viewBox="0 0 10 12" fill="currentColor">
              <rect x="1" y="1" width="3" height="10" rx="0.5" />
              <rect x="6" y="1" width="3" height="10" rx="0.5" />
            </svg>
          </button>
        ) : (
          <button
            className="pomo-btn bg-transparent border border-border-default rounded px-1.5 py-0.5 cursor-pointer text-text-secondary transition-all duration-150 hover:border-accent hover:text-accent flex items-center justify-center"
            id="pomoPauseBtn"
            title="Resume"
            onClick={onPomoResume}
          >
            <svg width="10" height="12" viewBox="0 0 10 12" fill="currentColor">
              <polygon points="1,1 9,6 1,11" />
            </svg>
          </button>
        )}
        <button
          className="pomo-btn pomo-stop bg-transparent border border-border-default rounded px-1.5 py-0.5 text-[0.72rem] cursor-pointer text-text-secondary transition-all duration-150 hover:border-priority-high hover:text-priority-high"
          id="pomoStopBtn"
          title="Stop"
          onClick={onPomoStop}
        >
          {'\u2715'}
        </button>
      </div>
    </div>
  )
}
