import { useState, useCallback } from 'react'
import VerticalResizablePanes from '../VerticalResizablePanes'
import GitGraph from './GitGraph'
import DiffViewer from '../DiffViewer'

interface DiffData {
  files: Array<{ path: string; diff: string }>
  stats: { additions: number; deletions: number }
}

/** What the graph has selected: one commit, or two being compared. */
interface Selection {
  commit: string | null
  compare: string | null
}

interface Props {
  sessionName?: string
  diffData: DiffData | null
  diffError?: string | null
  onRefreshDiff: () => void
  onFocusTerminal?: () => void
  onJumpToTodos?: () => void
  resetTrigger?: number
  maximized?: boolean
}

export default function GitTab({
  sessionName,
  diffData,
  diffError,
  onRefreshDiff,
  onFocusTerminal,
  onJumpToTodos,
  resetTrigger,
  maximized,
}: Props) {
  const [selection, setSelection] = useState<Selection>({ commit: null, compare: null })
  const [graphRefreshTrigger, setGraphRefreshTrigger] = useState(0)
  const [commitSelectVersion, setCommitSelectVersion] = useState(0)

  const handleSelectCommit = useCallback((hash: string | null, extend?: boolean) => {
    setSelection((prev) => {
      if (extend && hash && prev.commit && prev.commit !== hash) {
        return { commit: prev.commit, compare: hash }
      }
      const collapses = prev.commit === hash && prev.compare === null
      return { commit: collapses ? null : hash, compare: null }
    })
    setCommitSelectVersion((n) => n + 1)
  }, [])

  const handleGitAction = useCallback(() => {
    setGraphRefreshTrigger((n) => n + 1)
  }, [])

  return (
    <div data-testid="git-tab" className="h-full">
      <VerticalResizablePanes
        top={
          <GitGraph
            sessionName={sessionName}
            onSelectCommit={handleSelectCommit}
            selectedCommit={selection.commit}
            compareCommit={selection.compare}
            refreshTrigger={graphRefreshTrigger}
            resetTrigger={resetTrigger}
            onGitAction={handleGitAction}
            maximized={maximized}
          />
        }
        bottom={
          <DiffViewer
            sessionName={sessionName}
            diffData={diffData}
            diffError={diffError}
            onRefreshDiff={onRefreshDiff}
            onFocusTerminal={onFocusTerminal}
            onJumpToTodos={onJumpToTodos}
            selectedCommit={selection.commit}
            compareCommit={selection.compare}
            commitSelectVersion={commitSelectVersion}
            onGitAction={handleGitAction}
          />
        }
        defaultTopHeight={40}
        minTopHeight={15}
        maxTopHeight={75}
        storageKey={
          sessionName ? `lumbergh:gitTabSplitHeight:${sessionName}` : 'lumbergh:gitTabSplitHeight'
        }
      />
    </div>
  )
}
