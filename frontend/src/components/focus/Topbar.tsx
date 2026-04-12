import dayjs from 'dayjs'
import type { PomodoroState } from '../../types/focus'

interface TopbarProps {
  pomo: PomodoroState
  onPomoPause: () => void
  onPomoResume: () => void
  onPomoStop: () => void
  onOpenArchive: () => void
  onToggleShortcuts: () => void
  onToggleTheme: () => void
  themeName: string
}

function formatRemaining(remaining: number): string {
  return (
    String(Math.floor(remaining / 60)).padStart(2, '0') +
    ':' +
    String(remaining % 60).padStart(2, '0')
  )
}

export default function Topbar({
  pomo,
  onPomoPause,
  onPomoResume,
  onPomoStop,
  onOpenArchive,
  onToggleShortcuts,
  onToggleTheme,
  themeName,
}: TopbarProps) {
  return (
    <div className="topbar flex justify-between items-center px-8 py-3.5 border-b border-border-default shrink-0 bg-bg-base">
      <div className="topbar-left flex items-center gap-3">
        <h1 className="text-[1.1rem] font-bold tracking-tight text-navy">Focus Workspace</h1>
        <span className="date text-[0.82rem] text-text-muted font-medium" id="currentDate">
          {dayjs().format('ddd, MMM D')}
        </span>
      </div>

      <div
        className={`topbar-timer items-center gap-2 px-3 py-1 rounded-lg bg-orange-subtle border border-accent text-[0.8rem] font-semibold text-text-primary transition-opacity duration-200${pomo.phase === 'break' ? ' break' : ''}${pomo.active ? ' flex' : ' hidden'}`}
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
            className="pomo-btn bg-transparent border border-border-default rounded px-1.5 py-0.5 text-[0.72rem] cursor-pointer text-text-secondary transition-all duration-150 hover:border-accent hover:text-accent"
            id="pomoPauseBtn"
            title="Pause"
            onClick={onPomoPause}
          >
            {'\u25AE\u25AE'}
          </button>
        ) : (
          <button
            className="pomo-btn bg-transparent border border-border-default rounded px-1.5 py-0.5 text-[0.72rem] cursor-pointer text-text-secondary transition-all duration-150 hover:border-accent hover:text-accent"
            id="pomoPauseBtn"
            title="Resume"
            onClick={onPomoResume}
          >
            {'\u25B6'}
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

      <div className="topbar-actions flex items-center gap-2">
        <button className="topbar-btn" id="archiveBtn" title="View archive" onClick={onOpenArchive}>
          Archive
        </button>
        <button
          className="topbar-btn"
          id="shortcutHelpBtn"
          title="Keyboard shortcuts (?)"
          onClick={onToggleShortcuts}
        >
          ?
        </button>
        <button
          className="topbar-btn"
          id="themeToggle"
          title="Toggle theme"
          onClick={onToggleTheme}
        >
          {themeName === 'dark' ? 'Light' : 'Dark'}
        </button>
      </div>
    </div>
  )
}
