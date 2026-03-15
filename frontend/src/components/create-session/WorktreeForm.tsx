import DirectoryPicker from '../DirectoryPicker'
import BranchPicker from '../BranchPicker'

interface Props {
  parentRepo: string
  onParentRepoChange: (value: string) => void
  branch: string
  onBranchChange: (value: string) => void
  createNewBranch: boolean
  onCreateNewBranchChange: (value: boolean) => void
  onNewBranchNameChange: (value: string) => void
}

export default function WorktreeForm({
  parentRepo,
  onParentRepoChange,
  branch,
  onBranchChange,
  createNewBranch,
  onCreateNewBranchChange,
  onNewBranchNameChange,
}: Props) {
  return (
    <>
      <div>
        <label className="block text-sm text-text-tertiary mb-1">Parent Repository</label>
        <DirectoryPicker
          value={parentRepo}
          onChange={(path) => {
            onParentRepoChange(path)
            onBranchChange('')
          }}
          onManualEntry={() => {}}
        />
      </div>

      {parentRepo && (
        <div>
          <label className="block text-sm text-text-tertiary mb-1">Branch</label>
          <BranchPicker
            repoPath={parentRepo}
            value={branch}
            onChange={onBranchChange}
            onCreateNew={onNewBranchNameChange}
            createNewBranch={createNewBranch}
            onCreateNewBranchChange={onCreateNewBranchChange}
          />
        </div>
      )}
    </>
  )
}
