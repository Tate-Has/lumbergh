import { useState } from 'react'
import type { Task } from '../../types/focus'
import type { Repo } from '../../utils/repos'
import type { Worktree, RawSession } from '../../hooks/useWorktrees'

/**
 * WorktreePanel is presentational only. It does NOT call the send/poll/delete
 * APIs itself — all async orchestration belongs to the parent page, which must
 * own this state machine per worktree:
 *
 *   1. User clicks "Send to agent" here -> parent calls onSendWrapup(sessionName,
 *      promptText, worktreePath), POSTs to /api/session/{name}/send, and adds
 *      worktreePath to its `closingWorktreePaths` set.
 *   2. While closing, parent polls session idle-state (respecting the ~3s
 *      hysteresis grace period before trusting a poll) until the agent reports
 *      done, then moves worktreePath from `closingWorktreePaths` to
 *      `mergedWorktreePaths`.
 *   3. User clicks "Remove worktree" (post-merge) or "Clean up" (unlinked) ->
 *      parent calls onCleanupWorktree(repoPath, worktreePath), DELETEs the
 *      worktree, and (on success) calls refetch() from useWorktrees.
 *
 * This component just renders whichever of those three states a given row is
 * in, driven entirely by the closingWorktreePaths/mergedWorktreePaths props.
 */

export interface WorktreePanelProps {
  isOpen: boolean
  onToggleOpen: () => void
  repos: Repo[]
  worktreesByRepo: Record<string, Worktree[]>
  tasks: Task[]
  sessions: RawSession[]
  /** Worktree paths currently mid "commit + merge" send, per the state machine above. */
  closingWorktreePaths: Set<string>
  /** Worktree paths whose merge has completed and are awaiting removal. */
  mergedWorktreePaths: Set<string>
  onCleanupWorktree: (repoPath: string, worktreePath: string) => void
  onSendWrapup: (sessionName: string, promptText: string, worktreePath: string) => void
  onViewTask: (task: Task) => void
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return 'unknown'
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return 'unknown'
  const diffMs = Date.now() - then
  if (diffMs < 0) return 'just now'
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function defaultWrapupPrompt(branch: string): string {
  return `Commit all changes with a clear message, then merge ${branch} into main. Resolve any conflicts — this branch worked independently so conflicts should be minor (e.g. overlapping ID numbers); use your judgement.`
}

interface WorktreeRowProps {
  repoPath: string
  worktree: Worktree
  linkedTask: Task | undefined
  linkedSessionName: string | undefined
  isClosing: boolean
  isMerged: boolean
  onCleanupWorktree: (repoPath: string, worktreePath: string) => void
  onSendWrapup: (sessionName: string, promptText: string, worktreePath: string) => void
  onViewTask: (task: Task) => void
}

function WorktreeRow({
  repoPath,
  worktree,
  linkedTask,
  linkedSessionName,
  isClosing,
  isMerged,
  onCleanupWorktree,
  onSendWrapup,
  onViewTask,
}: WorktreeRowProps) {
  const [wrapupOpen, setWrapupOpen] = useState(false)
  const [draft, setDraft] = useState(() => defaultWrapupPrompt(worktree.branch))

  const isLinked = !!linkedTask && !!linkedSessionName

  return (
    <div className="worktree-row border-b border-border-subtle last:border-b-0 py-2.5">
      <div className="worktree-row-main flex items-center gap-3">
        <span className="worktree-branch font-mono text-[0.78rem] font-semibold text-purple shrink-0">
          {worktree.branch}
        </span>
        <span className="worktree-path font-mono text-[0.72rem] text-text-muted truncate flex-1 min-w-0">
          {worktree.path}
        </span>
        <span className="worktree-activity text-[0.68rem] text-text-tertiary shrink-0">
          {formatRelativeTime(worktree.last_activity)}
        </span>
        {worktree.stale && (
          <span className="worktree-stale-badge text-[0.6rem] font-bold uppercase tracking-[0.03em] text-status-error bg-status-error-bg rounded-[10px] px-2 py-0.5 shrink-0">
            Stale
          </span>
        )}
        <div className="worktree-row-actions flex items-center gap-1.5 shrink-0">
          {isClosing ? (
            <span className="worktree-merging flex items-center gap-1.5 text-[0.72rem] text-status-running">
              <span className="session-dot w-2 h-2 rounded-full shrink-0 bg-status-running animate-pulse" />
              Merging&hellip;
            </span>
          ) : isMerged ? (
            <>
              <span className="worktree-merged text-[0.72rem] font-semibold text-status-running">
                Merged &#10003;
              </span>
              <button
                className="text-[0.68rem] font-semibold px-2 py-1 rounded-md border border-border-subtle bg-bg-surface text-text-secondary cursor-pointer transition-all duration-100 hover:border-accent hover:text-accent"
                onClick={() => onCleanupWorktree(repoPath, worktree.path)}
              >
                Remove worktree
              </button>
            </>
          ) : isLinked ? (
            <>
              <button
                className="text-[0.68rem] font-semibold px-2 py-1 rounded-md border border-status-running bg-transparent text-status-running cursor-pointer transition-all duration-100 hover:bg-status-running-bg"
                onClick={() => setWrapupOpen((v) => !v)}
              >
                Close out
              </button>
              <button
                className="text-[0.68rem] font-semibold px-2 py-1 rounded-md border border-border-subtle bg-bg-surface text-text-secondary cursor-pointer transition-all duration-100 hover:border-accent hover:text-accent"
                onClick={() => linkedTask && onViewTask(linkedTask)}
              >
                View task
              </button>
            </>
          ) : (
            <button
              className="text-[0.68rem] font-semibold px-2 py-1 rounded-md border border-border-subtle bg-bg-surface text-text-secondary cursor-pointer transition-all duration-100 hover:border-status-error hover:text-status-error"
              onClick={() => onCleanupWorktree(repoPath, worktree.path)}
            >
              Clean up
            </button>
          )}
        </div>
      </div>
      {wrapupOpen && isLinked && !isClosing && !isMerged && (
        <div className="worktree-wrapup-panel mt-2 bg-bg-surface border border-border-subtle rounded-lg p-3">
          <textarea
            className="w-full h-[90px] text-[0.75rem] text-text-primary bg-bg-elevated border border-border-subtle rounded-md p-2 resize-none outline-none focus:border-accent"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex justify-end gap-1.5 mt-2">
            <button
              className="text-[0.68rem] font-semibold px-2.5 py-1 rounded-md border border-border-subtle bg-transparent text-text-secondary cursor-pointer hover:border-accent hover:text-accent"
              onClick={() => setWrapupOpen(false)}
            >
              Cancel
            </button>
            <button
              className="text-[0.68rem] font-semibold px-2.5 py-1 rounded-md border border-status-running-strong bg-status-running-strong text-white cursor-pointer hover:opacity-90"
              onClick={() => {
                if (!linkedSessionName) return
                onSendWrapup(linkedSessionName, draft, worktree.path)
                setWrapupOpen(false)
              }}
            >
              Send to agent
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function WorktreePanel({
  isOpen,
  onToggleOpen,
  repos,
  worktreesByRepo,
  tasks,
  sessions,
  closingWorktreePaths,
  mergedWorktreePaths,
  onCleanupWorktree,
  onSendWrapup,
  onViewTask,
}: WorktreePanelProps) {
  const totalWorktrees = repos.reduce(
    (sum, repo) => sum + (worktreesByRepo[repo.id]?.length || 0),
    0
  )

  function findLinkage(worktree: Worktree): {
    task: Task | undefined
    sessionName: string | undefined
  } {
    const session = sessions.find(
      (s) => s.workdir === worktree.path || s.worktreeParentRepo === worktree.path
    )
    if (!session) return { task: undefined, sessionName: undefined }
    const task = tasks.find((t) => t.session_name === session.name)
    return { task, sessionName: session.name }
  }

  return (
    <div
      className={`worktree-panel bg-bg-elevated border border-border-subtle rounded-xl overflow-hidden transition-[max-height] duration-[250ms] ease-[ease] shrink-0${isOpen ? ' max-h-[600px]' : ' collapsed max-h-[46px]'}`}
      id="worktreePanel"
    >
      <div
        className="worktree-panel-header flex items-center justify-between py-3 px-4 cursor-pointer select-none hover:bg-bg-surface"
        onClick={onToggleOpen}
      >
        <div className="flex items-center gap-2">
          <span className="section-title text-[0.85rem] font-semibold text-text-secondary uppercase tracking-[0.04em] m-0">
            Worktrees
          </span>
          <span className="section-count text-xs font-semibold text-text-muted bg-bg-surface rounded-[10px] px-2.5 py-0.5">
            {totalWorktrees}
          </span>
        </div>
        <span
          className={`worktree-panel-chevron text-xs text-text-muted transition-transform duration-200 ease-[ease] ${isOpen ? ' rotate-180' : ''}`}
        >
          &#9660;
        </span>
      </div>
      <div className="worktree-panel-body px-4 pb-4 overflow-y-auto">
        {repos.map((repo) => {
          const worktrees = worktreesByRepo[repo.id] || []
          if (worktrees.length === 0) return null
          return (
            <div key={repo.id} className="worktree-repo-group mb-3 last:mb-0">
              <div
                className="worktree-repo-name text-[0.7rem] font-semibold uppercase tracking-[0.04em] mb-1"
                style={{ color: repo.color }}
              >
                {repo.name}
              </div>
              {worktrees.map((worktree) => {
                const { task, sessionName } = findLinkage(worktree)
                return (
                  <WorktreeRow
                    key={worktree.path}
                    repoPath={repo.id}
                    worktree={worktree}
                    linkedTask={task}
                    linkedSessionName={sessionName}
                    isClosing={closingWorktreePaths.has(worktree.path)}
                    isMerged={mergedWorktreePaths.has(worktree.path)}
                    onCleanupWorktree={onCleanupWorktree}
                    onSendWrapup={onSendWrapup}
                    onViewTask={onViewTask}
                  />
                )
              })}
            </div>
          )
        })}
        {totalWorktrees === 0 && (
          <div className="empty-state text-[0.8rem] text-text-muted text-center p-5 italic">
            No worktrees found.
          </div>
        )}
      </div>
    </div>
  )
}
