interface NotesBarProps {
  content: string
  onChange: (content: string) => void
  isOpen: boolean
  onToggleOpen: () => void
}

export default function NotesBar({ content, onChange, isOpen, onToggleOpen }: NotesBarProps) {
  return (
    <div
      className={`notes-bar bg-bg-elevated border border-border-subtle rounded-xl overflow-hidden transition-[max-height] duration-[250ms] ease-[ease] shrink-0${isOpen ? ' max-h-[280px]' : ' collapsed max-h-[46px]'}`}
      id="notesBar"
    >
      <div
        className="notes-header flex items-center justify-between py-3 px-4 cursor-pointer select-none hover:bg-bg-surface"
        id="notesHeader"
        onClick={onToggleOpen}
      >
        <div className="notes-header-left flex items-center gap-2">
          <span className="section-title text-[0.85rem] font-semibold text-text-secondary uppercase tracking-[0.04em] m-0">
            Notes
          </span>
        </div>
        <span
          className={`notes-chevron text-xs text-text-muted transition-transform duration-200 ease-[ease] ${isOpen ? ' rotate-180' : ''}`}
        >
          &#9660;
        </span>
      </div>
      <textarea
        className="notes-textarea w-full h-[200px] px-4 pb-4 pt-2 bg-transparent border-none text-[0.82rem] text-text-primary resize-none outline-none leading-[1.6] placeholder:text-text-muted"
        id="notesTextarea"
        placeholder="Quick notes..."
        value={content}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}
