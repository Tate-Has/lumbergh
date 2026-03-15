import { useState } from 'react'

interface SessionUpdate {
  displayName?: string
  description?: string
}

interface Props {
  sessionName: string
  displayName: string | null
  description: string | null
  onSave: (name: string, updates: SessionUpdate) => void
  onCancel: () => void
}

export default function SessionCardEditForm({
  sessionName,
  displayName,
  description,
  onSave,
  onCancel,
}: Props) {
  const [editName, setEditName] = useState(displayName || sessionName)
  const [editDescription, setEditDescription] = useState(description || '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    e.stopPropagation()

    const updates: SessionUpdate = {}
    const trimmedName = editName.trim()
    const trimmedDesc = editDescription.trim()

    if (trimmedName !== (displayName || '')) {
      updates.displayName = trimmedName
    }
    if (trimmedDesc !== (description || '')) {
      updates.description = trimmedDesc
    }

    if (Object.keys(updates).length > 0) {
      onSave(sessionName, updates)
    }
    onCancel()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      className="bg-bg-surface rounded-lg p-4 border border-blue-500"
    >
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs text-text-tertiary mb-1">Display Name</label>
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
            className="w-full bg-control-bg text-text-primary px-2 py-1.5 rounded border border-border-subtle focus:border-blue-500 focus:outline-none text-sm"
            placeholder={sessionName}
          />
        </div>
        <div>
          <label className="block text-xs text-text-tertiary mb-1">Description</label>
          <input
            type="text"
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full bg-control-bg text-text-primary px-2 py-1.5 rounded border border-border-subtle focus:border-blue-500 focus:outline-none text-sm"
            placeholder="Optional description"
          />
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1 text-sm text-text-tertiary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
          >
            Save
          </button>
        </div>
      </form>
    </div>
  )
}
