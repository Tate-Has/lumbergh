import { useMemo, memo } from 'react'
import { Undo2, ChevronRight, Play } from 'lucide-react'
import type { DiffData } from './types'
import { getFileStats, reviewFilePrompt } from './utils'
import type { DiffHeader } from './utils'
import { useGitActions } from './useGitActions'
import FileListHeader from './FileListHeader'
import CommitForm from './CommitForm'

interface RemoteStatus {
  branch?: string
  remote?: string
  ahead: number
  behind: number
  error?: string
  httpAuthWarning?: string
  fetchFailed?: boolean
}

interface Props {
  data: DiffData
  sessionName?: string
  onSelectFile: (path: string) => void
  onRefresh: () => void
  commit?: DiffHeader | null
  onSendToTerminal?: (text: string, sendEnter: boolean) => void
  onGitAction?: () => void
  onExpand?: () => void
  remoteStatus?: RemoteStatus | null
  onFetch?: () => void
  onPull?: () => void
  isPulling?: boolean
}

const FileRow = memo(function FileRow({
  file,
  isWorkingChanges,
  revertingFile,
  onSelectFile,
  onRevertFile,
  onSendToTerminal,
}: {
  file: { path: string; diff: string }
  isWorkingChanges: boolean
  revertingFile: string | null
  onSelectFile: (path: string) => void
  onRevertFile: (path: string, e: React.MouseEvent) => void
  onSendToTerminal?: (text: string, sendEnter: boolean) => void
}) {
  const stats = useMemo(() => getFileStats(file.diff), [file.diff])
  return (
    <div
      onClick={() => onSelectFile(file.path)}
      data-testid="diff-file-item"
      className="group w-full flex items-center gap-3 px-3 py-2 hover:bg-bg-surface border-b border-border-default/50 text-left cursor-pointer"
    >
      <span className="text-action font-mono text-sm truncate flex-1">{file.path}</span>
      {onSendToTerminal && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onSendToTerminal(reviewFilePrompt(file.path), false)
          }}
          className="opacity-0 group-hover:opacity-100 px-1 py-0.5 text-text-muted hover:text-warning transition-all"
          title={`Ask the terminal to review ${file.path}`}
        >
          <Play size={14} />
        </button>
      )}
      {isWorkingChanges && (
        <button
          onClick={(e) => onRevertFile(file.path, e)}
          disabled={revertingFile === file.path}
          className="opacity-0 group-hover:opacity-100 px-1 py-0.5 text-text-muted hover:text-danger disabled:text-text-muted transition-all"
          title={`Revert ${file.path}`}
        >
          {revertingFile === file.path ? '...' : <Undo2 size={14} />}
        </button>
      )}
      <span className="text-success text-xs">+{stats.additions}</span>
      <span className="text-danger text-xs">-{stats.deletions}</span>
      <ChevronRight size={14} className="text-text-muted" />
    </div>
  )
})

const FileList = memo(function FileList({
  data,
  sessionName,
  onSelectFile,
  onRefresh,
  commit,
  onSendToTerminal,
  onGitAction,
  onExpand,
  remoteStatus,
  onFetch,
  onPull,
  isPulling,
}: Props) {
  const git = useGitActions({ sessionName, onRefresh, onGitAction })

  const isWorkingChanges = !commit
  const hasChanges = data.files.length > 0
  const sortedFiles = useMemo(
    () => [...data.files].sort((a, b) => a.path.localeCompare(b.path)),
    [data.files]
  )

  return (
    <div className="h-full flex flex-col">
      <FileListHeader
        data={data}
        sessionName={sessionName}
        commit={commit}
        onRefresh={onRefresh}
        onSendToTerminal={onSendToTerminal}
        onExpand={onExpand}
        remoteStatus={remoteStatus}
        onFetch={onFetch}
        onPull={onPull}
        isPulling={isPulling}
        gitBaseUrl={git.gitBaseUrl}
        isResetting={git.isResetting}
        isCommitting={git.isCommitting}
        isGenerating={git.isGenerating}
        isBranchOp={git.isBranchOp}
        hasChanges={hasChanges}
        onReset={git.handleReset}
        onBranchAction={git.handleBranchAction}
        onDeleteBranch={git.handleDeleteBranch}
        isDeletingBranch={git.isDeletingBranch}
      />

      {isWorkingChanges && (
        <CommitForm
          commitMessage={git.commitMessage}
          onCommitMessageChange={git.setCommitMessage}
          hasChanges={hasChanges}
          isCommitting={git.isCommitting}
          isPushing={git.isPushing}
          isGenerating={git.isGenerating}
          isResetting={git.isResetting}
          commitResult={git.commitResult}
          generateUrl={git.generateUrl}
          onCommit={git.handleCommit}
          onGenerate={git.handleGenerate}
          onMenuAction={git.handleMenuAction}
        />
      )}

      <div className="flex-1 overflow-auto">
        {sortedFiles.map((file) => (
          <FileRow
            key={file.path}
            file={file}
            isWorkingChanges={isWorkingChanges}
            revertingFile={git.revertingFile}
            onSelectFile={onSelectFile}
            onRevertFile={git.handleRevertFile}
            onSendToTerminal={onSendToTerminal}
          />
        ))}
      </div>
    </div>
  )
})

export default FileList
