interface Props {
  mineOnly: boolean
  /** False once a payload reports no resolvable git identity to filter by. */
  mineAvailable: boolean
  onToggleMineOnly: () => void
}

export default function GraphToolbar({ mineOnly, mineAvailable, onToggleMineOnly }: Props) {
  const active = mineOnly && mineAvailable

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs border-b border-border-default bg-bg-surface/50">
      <button
        data-testid="graph-mine-toggle"
        onClick={onToggleMineOnly}
        disabled={!mineAvailable}
        aria-pressed={mineOnly}
        title={
          mineAvailable
            ? 'Show only the trunk and branches you have worked on recently'
            : 'Set a git user.email, or add addresses under Settings, to filter by author'
        }
        className={`px-2 py-1 rounded-sm ring-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
          active
            ? 'bg-action/15 text-action ring-action/40'
            : 'bg-control-bg text-text-secondary ring-border-default hover:bg-control-bg-hover'
        }`}
      >
        Just mine
      </button>
      {active && <span className="text-text-muted">trunk + branches you have worked on</span>}
    </div>
  )
}
