import { useState } from 'react'
import type { Worktree } from '../../hooks/useWorktrees'

/**
 * Presentational only — collects the user's choice (existing worktree vs. new
 * branch name) and hands it to onLaunch. Does NOT call any session-creation
 * API itself; the parent owns that async call.
 *
 * Named export so this can be imported directly as a reference/reused shape by
 * other "launch agent" entry points (e.g. the Kanban card's inline mini-form)
 * without drift in the choice contract.
 */
export interface LaunchAgentChoice {
  worktreePath?: string
  newBranch?: string
}

export interface LaunchAgentFormProps {
  repoId: string
  existingWorktrees: Worktree[]
  onLaunch: (choice: LaunchAgentChoice) => void
  onCancel: () => void
}

export function LaunchAgentForm({
  repoId,
  existingWorktrees,
  onLaunch,
  onCancel,
}: LaunchAgentFormProps) {
  const [selectedWorktree, setSelectedWorktree] = useState('')
  const [newBranch, setNewBranch] = useState('')

  const canSubmit = selectedWorktree !== '' || newBranch.trim() !== ''

  function handleSubmit(e: React.MouseEvent) {
    e.stopPropagation()
    if (!canSubmit) return
    onLaunch({
      worktreePath: selectedWorktree || undefined,
      newBranch: selectedWorktree ? undefined : newBranch.trim() || undefined,
    })
  }

  function handleCancel(e: React.MouseEvent) {
    e.stopPropagation()
    onCancel()
  }

  return (
    <div
      className="launch-agent-form flex flex-col gap-1.5"
      data-repo-id={repoId}
      onClick={(e) => e.stopPropagation()}
    >
      <select
        className="w-full text-[0.72rem] px-1.5 py-1 rounded-md border border-border-default bg-bg-elevated text-text-primary outline-none focus:border-accent"
        value={selectedWorktree}
        onChange={(e) => setSelectedWorktree(e.target.value)}
      >
        <option value="">New branch&hellip;</option>
        {existingWorktrees.map((wt) => (
          <option key={wt.path} value={wt.path}>
            {wt.branch}
            {wt.is_main ? ' (main)' : ''}
          </option>
        ))}
      </select>
      {!selectedWorktree && (
        <input
          type="text"
          placeholder="new-branch-name"
          value={newBranch}
          onChange={(e) => setNewBranch(e.target.value)}
          className="w-full text-[0.72rem] px-1.5 py-1 rounded-md border border-border-default bg-bg-elevated text-text-primary outline-none focus:border-accent"
        />
      )}
      <div className="flex gap-1.5">
        <button
          className="flex-1 text-[0.65rem] font-semibold px-2 py-1 rounded-md border border-status-running text-status-running bg-status-running-bg cursor-pointer transition-all duration-100 hover:opacity-80 disabled:opacity-40 disabled:cursor-default"
          disabled={!canSubmit}
          onClick={handleSubmit}
        >
          Launch
        </button>
        <button
          className="text-[0.65rem] font-semibold px-2 py-1 rounded-md border border-border-default text-text-secondary bg-bg-elevated cursor-pointer transition-all duration-100 hover:border-accent hover:text-accent"
          onClick={handleCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
