// Small rounded pill showing a session name, colored deterministically by
// hashing the name into a fixed 8-hue palette (--session-tag-N-bg/-fg tokens
// in index.css, defined per-theme so contrast holds in both light and dark).
// Also functions as a click-to-toggle filter chip: clicking a tag (either the
// standalone filter row or the one embedded in a card's header) toggles that
// session's visibility in the combined feed.

const PALETTE_SIZE = 8

/** Simple deterministic string hash (djb2-ish), stable across reloads/sessions. */
function hashString(value: string): number {
  let hash = 5381
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 33) ^ value.charCodeAt(i)
  }
  return Math.abs(hash)
}

function sessionTagPaletteIndex(sessionName: string): number {
  return (hashString(sessionName) % PALETTE_SIZE) + 1
}

interface SessionTagProps {
  session: string
  active?: boolean
  onToggle?: (session: string) => void
  className?: string
}

export default function SessionTag({
  session,
  active = true,
  onToggle,
  className = '',
}: SessionTagProps) {
  const idx = sessionTagPaletteIndex(session)
  return (
    <button
      type="button"
      onClick={
        onToggle
          ? (e) => {
              e.stopPropagation()
              onToggle(session)
            }
          : undefined
      }
      title={onToggle ? `Toggle "${session}" filter` : session}
      className={`inline-flex max-w-[10rem] shrink-0 items-center rounded-full px-2 py-0.5 text-[0.68rem] font-semibold truncate transition-opacity duration-150 ${onToggle ? 'cursor-pointer' : 'cursor-default'} ${active ? '' : 'opacity-40'} ${className}`}
      style={{
        background: `var(--session-tag-${idx}-bg)`,
        color: `var(--session-tag-${idx}-fg)`,
      }}
    >
      {session}
    </button>
  )
}
