import Modal from '../ui/Modal'
import WorktreeList from './WorktreeList'
import { useWorktrees } from '../../hooks/useWorktrees'
/** The worktrees of this session's repo, on demand.
 *
 * Owns its own fetch rather than taking a list: the graph payload's worktree
 * entries are enough to count for the toolbar button, but not to manage — and
 * the list has to reload itself after a reap. */
export default function WorktreeOverlay({
  open,
  sessionName,
  onClose,
}: {
  open: boolean
  sessionName?: string
  onClose: () => void
}) {
  if (!open || !sessionName) return null
  return <WorktreeOverlayBody sessionName={sessionName} onClose={onClose} />
}

function WorktreeOverlayBody({
  sessionName,
  onClose,
}: {
  sessionName: string
  onClose: () => void
}) {
  const { worktrees, refresh } = useWorktrees(sessionName)

  return (
    <Modal open onClose={onClose} title="Worktrees">
      <p className="text-xs text-text-muted mb-3">
        Each of these has a branch checked out. Git refuses to check that branch out anywhere else
        until the worktree is gone.
      </p>
      <WorktreeList worktrees={worktrees} onChanged={refresh} currentSession={sessionName} />
    </Modal>
  )
}
