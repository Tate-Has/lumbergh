interface ToolbarProps {
  groupByRepo: boolean
  onSetGroupByRepo: (v: boolean) => void
  worktreeCount: number
  worktreePanelOpen: boolean
  onToggleWorktreePanel: () => void
  onAddTask: () => void
  onOpenArchive: () => void
  filterDropdowns: React.ReactNode
}

export default function Toolbar({
  groupByRepo,
  onSetGroupByRepo,
  worktreeCount,
  worktreePanelOpen,
  onToggleWorktreePanel,
  onAddTask,
  onOpenArchive,
  filterDropdowns,
}: ToolbarProps) {
  return (
    <div className="board-toolbar flex items-center justify-between gap-3 flex-wrap mb-4">
      <div className="board-toolbar-segment inline-flex items-center bg-bg-elevated border border-border-default rounded-lg p-0.5 shrink-0">
        <button
          type="button"
          className={`text-[0.85rem] font-semibold px-3 py-1 rounded-md cursor-pointer transition-all duration-150 ease-in-out${groupByRepo ? ' bg-bg-surface text-accent shadow-low' : ' text-text-muted hover:text-text-secondary'}`}
          onClick={() => onSetGroupByRepo(true)}
        >
          Repo lanes
        </button>
        <button
          type="button"
          className={`text-[0.85rem] font-semibold px-3 py-1 rounded-md cursor-pointer transition-all duration-150 ease-in-out${!groupByRepo ? ' bg-bg-surface text-accent shadow-low' : ' text-text-muted hover:text-text-secondary'}`}
          onClick={() => onSetGroupByRepo(false)}
        >
          Flat board
        </button>
      </div>

      <div className="board-toolbar-actions flex items-center gap-2 flex-wrap">
        {filterDropdowns}
        <button
          type="button"
          className={`topbar-btn${worktreePanelOpen ? ' !bg-orange-subtle !border-accent !text-accent' : ''}`}
          onClick={onToggleWorktreePanel}
        >
          Worktrees ({worktreeCount})
        </button>
        <button type="button" className="topbar-btn" onClick={onOpenArchive}>
          Archive
        </button>
        <button
          type="button"
          className="text-[0.85rem] font-semibold text-white bg-accent border border-accent rounded-md px-3 py-1 cursor-pointer transition-all duration-150 ease-in-out hover:bg-accent-hover"
          onClick={onAddTask}
        >
          + New task
        </button>
      </div>
    </div>
  )
}
