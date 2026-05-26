export interface FilterItem {
  key: string
  label: string
  selected: boolean
}

export interface FilterDropdownProps {
  id: string
  buttonId: string
  menuId: string
  label: string
  items: FilterItem[]
  activeCount: number
  totalCount: number
  onToggleItem: (key: string) => void
  onClearAll?: () => void
  isOpen: boolean
  onToggleOpen: () => void
}

export default function FilterDropdown({
  id,
  buttonId,
  menuId,
  label,
  items,
  activeCount,
  totalCount,
  onToggleItem,
  onClearAll,
  isOpen,
  onToggleOpen,
}: FilterDropdownProps) {
  const hasFilter = activeCount > 0 && activeCount < totalCount

  const buttonText = hasFilter ? `${label} (${activeCount}) \u25BE` : `${label} \u25BE`

  return (
    <div className="filter-dropdown relative" id={id}>
      <button
        className={`filter-btn bg-transparent border border-border-default rounded-md py-1 px-3 text-[0.72rem] font-semibold text-text-secondary cursor-pointer transition-all duration-150 ease-[ease] hover:border-accent hover:text-accent${hasFilter ? ' has-filter bg-orange-subtle border-accent text-accent' : ''}`}
        id={buttonId}
        type="button"
        onClick={onToggleOpen}
      >
        {buttonText}
      </button>
      <div
        className={`filter-menu absolute top-[calc(100%+4px)] right-0 min-w-[160px] bg-bg-elevated border border-border-default rounded-lg shadow-modal z-50 py-1 max-h-[260px] overflow-y-auto${isOpen ? ' open block' : ' hidden'}`}
        id={menuId}
      >
        {onClearAll && (
          <>
            <div
              className="filter-menu-item clear-item flex items-center gap-2 py-1.5 px-3 text-[0.72rem] font-medium text-text-muted cursor-pointer transition-[background] duration-100 hover:bg-bg-surface"
              onClick={onClearAll}
            >
              Show all
            </div>
            {items.length > 0 && <div className="filter-menu-divider h-px bg-border-subtle my-1" />}
          </>
        )}
        {items.map((item) => (
          <div
            className={`filter-menu-item flex items-center gap-2.5 py-2 px-3.5 text-[0.78rem] font-medium text-text-primary cursor-pointer transition-[background] duration-100 hover:bg-bg-surface${item.selected ? ' selected' : ''}`}
            key={item.key}
            onClick={() => onToggleItem(item.key)}
          >
            <span
              className={`check-mark w-3.5 h-3.5 border-2 border-border-default rounded-[3px] flex items-center justify-center shrink-0 transition-all duration-150${item.selected ? ' bg-accent border-accent' : ''}`}
            />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
