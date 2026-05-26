import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { getApiBase } from '../../../config'
import type { Task } from '../../../types/focus'
import ModeToggle from '../../create-session/ModeToggle'
import ExistingRepoForm from '../../create-session/ExistingRepoForm'
import NewRepoForm from '../../create-session/NewRepoForm'
import WorktreeForm from '../../create-session/WorktreeForm'
import AgentProviderSelect from '../../create-session/AgentProviderSelect'

interface Props {
  isOpen: boolean
  task: Task | null
  onClose: () => void
  onSessionCreated: (sessionName: string) => void
}

type SessionMode = 'existing' | 'new' | 'worktree'
type DirStatus = 'unchecked' | 'checking' | 'exists' | 'not_found' | 'error'

function toSlug(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s_-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

function deriveSlug(
  name: string,
  mode: SessionMode,
  workdir: string,
  projectSlug: string,
  parentRepo: string
): string {
  const lastSegment = (path: string) => toSlug(path.split('/').filter(Boolean).pop() || '')
  if (toSlug(name)) return toSlug(name)
  if (mode === 'existing') return lastSegment(workdir)
  if (mode === 'new') return projectSlug
  return lastSegment(parentRepo)
}

export default function CreateSessionModal({ isOpen, task, onClose, onSessionCreated }: Props) {
  const [mode, setMode] = useState<SessionMode>('existing')
  const [name, setName] = useState('')
  const [workdir, setWorkdir] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [manualEntry, setManualEntry] = useState(false)
  const [dirStatus, setDirStatus] = useState<DirStatus>('unchecked')

  // New repo mode state
  const [projectName, setProjectName] = useState('')
  const [parentDir, setParentDir] = useState('')
  const [editingParentDir, setEditingParentDir] = useState(false)

  // Worktree mode state
  const [parentRepo, setParentRepo] = useState('')
  const [branch, setBranch] = useState('')
  const [createNewBranch, setCreateNewBranch] = useState(false)
  const [newBranchName, setNewBranchName] = useState('')

  // Agent provider state
  const [agentProvider, setAgentProvider] = useState<string>('')
  const [agentProviders, setAgentProviders] = useState<Record<string, { label: string }>>({})
  const [defaultAgent, setDefaultAgent] = useState<string>('')

  // Tab visibility state
  const [customizeTabs, setCustomizeTabs] = useState(false)
  const [globalTabVisibility, setGlobalTabVisibility] = useState<Record<string, boolean>>({
    git: true,
    files: true,
    todos: true,
    prompts: true,
    shared: true,
  })
  const [tabVisibility, setTabVisibility] = useState<Record<string, boolean>>({
    git: true,
    files: true,
    todos: true,
    prompts: true,
    shared: true,
  })

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setMode('existing')
      setName('')
      setWorkdir('')
      setDescription(task?.title || '')
      setError(null)
      setIsCreating(false)
      setManualEntry(false)
      setDirStatus('unchecked')
      setProjectName('')
      setEditingParentDir(false)
      setParentRepo('')
      setBranch('')
      setCreateNewBranch(false)
      setNewBranchName('')
      setAgentProvider('')
      setCustomizeTabs(false)
    }
  }, [isOpen, task])

  // Fetch Lumbergh settings on mount
  useEffect(() => {
    if (!isOpen) return
    fetch(`${getApiBase()}/settings`)
      .then((res) => res.json())
      .then((data) => {
        if (data.repoSearchDir) setParentDir(data.repoSearchDir)
        if (data.agentProviders) setAgentProviders(data.agentProviders)
        if (data.defaultAgent) setDefaultAgent(data.defaultAgent)
        if (data.tabVisibility) {
          setGlobalTabVisibility(data.tabVisibility)
          setTabVisibility(data.tabVisibility)
        }
      })
      .catch(() => {})
  }, [isOpen])

  const projectSlug = toSlug(projectName)
  const newRepoPath = parentDir && projectSlug ? `${parentDir}/${projectSlug}` : ''
  const slug = deriveSlug(name, mode, workdir, projectSlug, parentRepo)

  // Debounced directory validation for manual entry
  useEffect(() => {
    if (!manualEntry || !workdir.trim() || mode !== 'existing') {
      setDirStatus('unchecked')
      return
    }
    setDirStatus('checking')
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `${getApiBase()}/directories/validate?path=${encodeURIComponent(workdir.trim())}`
        )
        const data = await res.json()
        setDirStatus(data.exists ? 'exists' : 'not_found')
      } catch {
        setDirStatus('error')
      }
    }, 400)
    return () => clearTimeout(timer)
  }, [workdir, manualEntry, mode])

  const isValid = () => {
    if (!slug) return false
    if (mode === 'existing') {
      if (!workdir.trim()) return false
      if (manualEntry && dirStatus === 'not_found') return false
      if (manualEntry && dirStatus === 'checking') return false
      return true
    }
    if (mode === 'new') {
      return projectSlug !== '' && parentDir.trim() !== ''
    }
    return (
      parentRepo.trim() !== '' && (createNewBranch ? newBranchName.trim() !== '' : branch !== '')
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid()) return

    setIsCreating(true)
    setError(null)

    try {
      const body: Record<string, unknown> = {
        name: slug,
        description: description.trim(),
      }

      if (agentProvider && agentProvider !== defaultAgent) {
        body.agent_provider = agentProvider
      }
      if (customizeTabs) {
        body.tab_visibility = tabVisibility
      }

      if (mode === 'existing') {
        body.mode = 'direct'
        body.workdir = workdir.trim()
      } else if (mode === 'new') {
        body.mode = 'direct'
        body.workdir = newRepoPath
        body.init_repo = true
      } else {
        body.mode = 'worktree'
        body.worktree = {
          parent_repo: parentRepo.trim(),
          branch: createNewBranch ? newBranchName.trim() : branch,
          create_branch: createNewBranch,
        }
      }

      const res = await fetch(`${getApiBase()}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to create session')
      }

      onSessionCreated(slug)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session')
    } finally {
      setIsCreating(false)
    }
  }

  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className={`modal-overlay fixed inset-0 bg-black/40 items-center justify-center z-[100] ${isOpen ? 'active flex' : 'hidden'}`}
      data-testid="create-session-modal-overlay"
      onClick={handleOverlayClick}
    >
      <div className="modal bg-bg-elevated border border-border-default rounded-xl w-full max-w-md shadow-modal">
        <div className="flex items-center justify-between p-4 border-b border-border-default">
          <h2 className="text-lg font-semibold text-text-primary">New Session</h2>
          <button
            onClick={onClose}
            className="text-text-tertiary hover:text-text-primary transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {task && (
          <div className="session-task-name text-[0.85rem] font-semibold text-text-primary mx-4 mt-4 py-2 px-2.5 bg-bg-surface rounded-md border border-border-subtle">
            {task.title}
          </div>
        )}

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <ModeToggle mode={mode} onModeChange={setMode} />

          {mode !== 'new' && (
            <div>
              <label className="block text-sm text-text-tertiary mb-1">
                Session Name <span className="text-text-muted font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={
                  workdir
                    ? workdir.split('/').filter(Boolean).pop() || 'auto'
                    : 'auto from directory'
                }
                data-testid="session-name-input"
                className="w-full px-3 py-2 bg-input-bg text-text-primary rounded border border-input-border focus:outline-none focus:border-blue-500"
              />
              {slug && (
                <p className="text-xs text-text-muted mt-1">
                  Session ID: <span className="text-text-tertiary font-mono">{slug}</span>
                </p>
              )}
            </div>
          )}

          {mode === 'existing' ? (
            <ExistingRepoForm
              workdir={workdir}
              onWorkdirChange={setWorkdir}
              manualEntry={manualEntry}
              onManualEntryChange={setManualEntry}
              dirStatus={dirStatus}
            />
          ) : mode === 'new' ? (
            <NewRepoForm
              projectName={projectName}
              onProjectNameChange={setProjectName}
              projectSlug={projectSlug}
              parentDir={parentDir}
              onParentDirChange={setParentDir}
              editingParentDir={editingParentDir}
              onEditingParentDirChange={setEditingParentDir}
              newRepoPath={newRepoPath}
              slug={slug}
            />
          ) : (
            <WorktreeForm
              parentRepo={parentRepo}
              onParentRepoChange={setParentRepo}
              branch={branch}
              onBranchChange={setBranch}
              createNewBranch={createNewBranch}
              onCreateNewBranchChange={setCreateNewBranch}
              onNewBranchNameChange={setNewBranchName}
            />
          )}

          <div>
            <label className="block text-sm text-text-tertiary mb-1">Description (optional)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Working on user authentication"
              data-testid="session-description-input"
              className="w-full px-3 py-2 bg-input-bg text-text-primary rounded border border-input-border focus:outline-none focus:border-blue-500"
            />
          </div>

          <AgentProviderSelect
            agentProviders={agentProviders}
            agentProvider={agentProvider}
            defaultAgent={defaultAgent}
            onAgentProviderChange={setAgentProvider}
          />

          <div>
            <label className="flex items-center gap-2 text-sm text-text-tertiary">
              <input
                type="checkbox"
                checked={customizeTabs}
                onChange={() => {
                  if (customizeTabs) setTabVisibility(globalTabVisibility)
                  setCustomizeTabs(!customizeTabs)
                }}
                className="rounded border-input-border bg-input-bg"
              />
              Customize visible tabs
            </label>
            {customizeTabs && (
              <div className="mt-2 ml-6 space-y-2">
                <label className="flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={Object.values(tabVisibility).every((v) => !v)}
                    onChange={() => {
                      const allOff = Object.values(tabVisibility).every((v) => !v)
                      if (allOff) {
                        setTabVisibility(globalTabVisibility)
                      } else {
                        setTabVisibility(
                          Object.fromEntries(Object.keys(tabVisibility).map((k) => [k, false]))
                        )
                      }
                    }}
                    className="rounded border-input-border bg-input-bg"
                  />
                  <span className="text-text-secondary font-medium">Terminal only</span>
                </label>
                <div className="flex flex-wrap gap-3">
                  {(
                    [
                      ['git', 'Git'],
                      ['files', 'Files'],
                      ['todos', 'Todos'],
                      ['prompts', 'Prompts'],
                      ['shared', 'Shared'],
                    ] as const
                  ).map(([key, label]) => {
                    const isEnabled = tabVisibility[key] !== false
                    return (
                      <label key={key} className="flex items-center gap-1.5 text-sm">
                        <input
                          type="checkbox"
                          checked={isEnabled}
                          onChange={() =>
                            setTabVisibility((prev) => ({ ...prev, [key]: !prev[key] }))
                          }
                          className="rounded border-input-border bg-input-bg"
                        />
                        <span className="text-text-secondary">{label}</span>
                      </label>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {error && <div className="text-red-400 text-sm">{error}</div>}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-text-tertiary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating || !isValid()}
              data-testid="create-session-submit"
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-control-bg-hover disabled:cursor-not-allowed text-white rounded transition-colors"
            >
              {isCreating ? 'Creating...' : 'Create Session'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
