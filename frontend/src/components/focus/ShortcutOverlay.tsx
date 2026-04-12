export interface ShortcutOverlayProps {
  isOpen: boolean
  onClose: () => void
}

const SHORTCUTS = [
  { key: 'n', description: 'Focus inbox input' },
  { key: 't', description: 'Scroll to Today' },
  { key: 'd', description: 'Toggle theme' },
  { key: 'Esc', description: 'Close modal / dropdown' },
  { key: '?', description: 'Show this help' },
]

export default function ShortcutOverlay({ isOpen, onClose }: ShortcutOverlayProps) {
  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div
      className={`shortcut-overlay fixed inset-0 bg-black/40 items-center justify-center z-[100] ${isOpen ? ' active flex' : ' hidden'}`}
      id="shortcutOverlay"
      onClick={handleOverlayClick}
    >
      <div className="shortcut-modal bg-bg-elevated border border-border-default rounded-xl p-6 w-[340px] max-w-[90vw] shadow-modal">
        <h3 className="mb-4 text-base font-semibold">Keyboard Shortcuts</h3>
        <div className="shortcut-list flex flex-col gap-2.5">
          {SHORTCUTS.map((s) => (
            <div className="shortcut-row flex items-center gap-3" key={s.key}>
              <kbd className="inline-flex items-center justify-center min-w-8 h-7 px-2 bg-bg-surface border border-border-default rounded-md font-['Archivo',sans-serif] text-[13px] font-semibold text-text-primary">
                {s.key}
              </kbd>
              <span className="text-text-secondary text-sm">{s.description}</span>
            </div>
          ))}
        </div>
        <button
          className="topbar-btn mt-5 w-full"
          id="shortcutClose"
          type="button"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </div>
  )
}
