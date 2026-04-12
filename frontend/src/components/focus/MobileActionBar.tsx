interface MobileActionBarProps {
  onAddToday: () => void
  onAddInbox: () => void
  onScrollToBoard: () => void
}

export default function MobileActionBar({
  onAddToday,
  onAddInbox,
  onScrollToBoard,
}: MobileActionBarProps) {
  return (
    <div className="mobile-action-bar" id="mobileActionBar">
      <button className="mobile-action-btn" id="mobileAddToday" onClick={onAddToday}>
        + Today
      </button>
      <button className="mobile-action-btn" id="mobileAddInbox" onClick={onAddInbox}>
        + Inbox
      </button>
      <button className="mobile-action-btn" id="mobileScrollBoard" onClick={onScrollToBoard}>
        Board
      </button>
    </div>
  )
}
