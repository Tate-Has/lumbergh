interface ConfirmDialogProps {
  isOpen: boolean
  message: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  isOpen,
  message,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <div
      id="confirmDialog"
      className={`fixed inset-0 z-[200] flex items-center justify-center bg-bg-overlay transition-opacity${isOpen ? ' opacity-100' : ' opacity-0 pointer-events-none'}`}
      onClick={onCancel}
    >
      <div
        className="bg-bg-elevated border border-border-default rounded-lg p-6 shadow-modal max-w-sm w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <p id="confirmDialogMessage" className="text-text-primary text-sm mb-6">
          {message}
        </p>
        <div className="flex justify-end gap-3">
          <button
            id="confirmDialogCancel"
            className="modal-btn bg-transparent border border-border-default rounded-md px-4 py-2 text-sm font-semibold text-text-secondary cursor-pointer hover:bg-bg-surface transition-colors"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            id="confirmDialogConfirm"
            className="modal-btn bg-accent border border-accent rounded-md px-4 py-2 text-sm font-semibold text-white cursor-pointer hover:bg-accent-hover transition-colors"
            onClick={onConfirm}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
