import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import Button from './ui/Button'
import { getApiBase } from '../config'
import ModeToggle from './create-session/ModeToggle'
import ExistingRepoForm from './create-session/ExistingRepoForm'
import NewRepoForm from './create-session/NewRepoForm'
import WorktreeForm from './create-session/WorktreeForm'
import AgentProviderSelect from './create-session/AgentProviderSelect'

interface Props {
  onClose: () => void
  onCreated: () => void
  /** Open on a given tab — "worktree" when spawning from a session you are in. */
  initialMode?: SessionMode
  /** Prefill the repo a worktree branches from. */
  initialParentRepo?: string
  /** Branch this session's conversation into the new one. */
  forkFrom?: string
}

type SessionMode = 'existing' | 'new' | 'worktree'
type DirStatus = 'unchecked' | 'checking' | 'exists' | 'not_found' | 'error'

async function postSession(
  body: Record<string, unknown>
): Promise<{ name: string; existing?: boolean }> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 15000)
  let res: Response
  try {
    res = await fetch(`${getApiBase()}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
  } catch (fetchErr) {
    if ((fetchErr as Error).name === 'AbortError') {
      throw new Error('Request timed out after 15s — the backend may be unresponsive.')
    }
    throw fetchErr
  } finally {
    clearTimeout(timeoutId)
  }

  if (!res.ok) {
    let detail = `Server returned ${res.status}`
    try {
      const data = await res.json()
      if (data.detail) detail = data.detail
    } catch {
      const text = await res.text().catch(() => '')
      if (text) detail = text
    }
    throw new Error(detail)
  }
  return res.json()
}

// Generate a URL-safe slug from free-form text
function toSlug(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s_-]/g, '') // Remove invalid characters
    .replace(/\s+/g, '-') // Replace spaces with hyphens
    .replace(/-+/g, '-') // Collapse multiple hyphens
    .replace(/^-|-$/g, '') // Trim leading/trailing hyphens
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

/** What the dialog opens on — a plain "New Session", or prefilled for a spawn
 * or a fork from the session you were just in. */
function openingState(initialMode?: SessionMode, initialParentRepo?: string) {
  return { mode: initialMode ?? 'existing', parentRepo: initialParentRepo ?? '' }
}

function modalTitle(forkFrom?: string): string {
  return forkFrom ? 'Fork Session' : 'New Session'
}

/** Enter outside a field — a keyboard user whose focus fell to the body after
 * picking a repo — should still create the session. Fields keep the browser's
 * own implicit submission, so handling those here would submit twice. */
function isBareEnter(e: KeyboardEvent): boolean {
  if (e.key !== 'Enter' || e.defaultPrevented) return false
  if (e.shiftKey || e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return false
  const target = e.target as HTMLElement | null
  return !target?.closest?.('input, textarea, select, button, a, [contenteditable]')
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Failed to create session'
}

/** The optional half of the payload: only send what differs from the defaults. */
function optionsPayload(f: {
  agentProvider: string
  defaultAgent: string
  customizeTabs: boolean
  tabVisibility: Record<string, boolean>
  forkFrom?: string
}): Record<string, unknown> {
  return {
    ...(f.agentProvider && f.agentProvider !== f.defaultAgent
      ? { agent_provider: f.agentProvider }
      : {}),
    ...(f.customizeTabs ? { tab_visibility: f.tabVisibility } : {}),
    ...(f.forkFrom ? { fork_from: f.forkFrom } : {}),
  }
}

/** Whether the form has everything the chosen mode needs. */
function canSubmit(
  mode: SessionMode,
  f: {
    slug: string
    workdir: string
    manualEntry: boolean
    dirStatus: DirStatus
    projectSlug: string
    parentDir: string
    parentRepo: string
    branch: string
    createNewBranch: boolean
    newBranchName: string
  }
): boolean {
  if (!f.slug) return false
  if (mode === 'existing') {
    if (!f.workdir.trim()) return false
    return !(f.manualEntry && (f.dirStatus === 'not_found' || f.dirStatus === 'checking'))
  }
  if (mode === 'new') {
    return f.projectSlug !== '' && f.parentDir.trim() !== ''
  }
  return (
    f.parentRepo.trim() !== '' &&
    (f.createNewBranch ? f.newBranchName.trim() !== '' : f.branch !== '')
  )
}

/** Where the new session lives — the half of the payload the mode decides. */
function locationPayload(
  mode: SessionMode,
  fields: {
    workdir: string
    newRepoPath: string
    parentRepo: string
    branch: string
    createNewBranch: boolean
    newBranchName: string
  }
): Record<string, unknown> {
  if (mode === 'existing') {
    return { mode: 'direct', workdir: fields.workdir.trim() }
  }
  if (mode === 'new') {
    return { mode: 'direct', workdir: fields.newRepoPath, init_repo: true }
  }
  return {
    mode: 'worktree',
    worktree: {
      parent_repo: fields.parentRepo.trim(),
      branch: fields.createNewBranch ? fields.newBranchName.trim() : fields.branch,
      create_branch: fields.createNewBranch,
    },
  }
}

/** Says what a fork inherits, so "New Session" and "Fork Session" are not the
 * same dialog with a different heading. */
function ForkNotice({ forkFrom }: { forkFrom?: string }) {
  if (!forkFrom) return null
  return (
    <p
      className="text-sm text-text-tertiary bg-control-bg rounded-[var(--radius-md)] px-3 py-2"
      data-testid="fork-notice"
    >
      Starts from <span className="text-text-primary font-medium">{forkFrom}</span>&rsquo;s
      conversation so far, branched — that session keeps going untouched.
    </p>
  )
}

export default function CreateSessionModal({
  onClose,
  onCreated,
  initialMode,
  initialParentRepo,
  forkFrom,
}: Props) {
  const initial = openingState(initialMode, initialParentRepo)
  const navigate = useNavigate()
  const [mode, setMode] = useState<SessionMode>(initial.mode)
  const [name, setName] = useState('')
  const [workdir, setWorkdir] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [manualEntry, setManualEntry] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)

  const [dirStatus, setDirStatus] = useState<DirStatus>('unchecked')

  // New repo mode state
  const [projectName, setProjectName] = useState('')
  const [parentDir, setParentDir] = useState('')
  const [editingParentDir, setEditingParentDir] = useState(false)

  // Worktree mode state
  const [parentRepo, setParentRepo] = useState(initial.parentRepo)
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

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!isBareEnter(e)) return
      e.preventDefault()
      formRef.current?.requestSubmit()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  // Fetch settings (repoSearchDir + agent providers)
  useEffect(() => {
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
  }, [])

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

  const isValid = () =>
    canSubmit(mode, {
      slug,
      workdir,
      manualEntry,
      dirStatus,
      projectSlug,
      parentDir,
      parentRepo,
      branch,
      createNewBranch,
      newBranchName,
    })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid()) return

    setIsCreating(true)
    setError(null)

    try {
      const body: Record<string, unknown> = {
        name: slug,
        description: description.trim(),
        ...optionsPayload({ agentProvider, defaultAgent, customizeTabs, tabVisibility, forkFrom }),
      }

      Object.assign(
        body,
        locationPayload(mode, {
          workdir,
          newRepoPath,
          parentRepo,
          branch,
          createNewBranch,
          newBranchName,
        })
      )

      const data = await postSession(body)
      // An already-existing session is not an error: just go to it, without
      // telling the caller a session was created.
      if (!data.existing) onCreated()
      onClose()
      navigate(`/session/${data.name}`)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-bg-overlay backdrop-blur-[8px] flex items-center justify-center z-50 p-4">
      <div
        className="bg-bg-surface rounded-[var(--radius-2xl)] shadow-[var(--shadow-high)] w-full max-w-md border border-border-default"
        data-testid="create-session-modal"
      >
        <div className="flex items-center justify-between p-4 border-b border-border-default">
          <h2 className="text-lg font-semibold text-text-primary">{modalTitle(forkFrom)}</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-control-bg hover:bg-control-bg-hover flex items-center justify-center text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        <form ref={formRef} onSubmit={handleSubmit} className="p-4 space-y-4">
          <ForkNotice forkFrom={forkFrom} />
          <ModeToggle mode={mode} onModeChange={setMode} />

          {mode !== 'new' && (
            /* Session Name - not shown for New Repo (project name drives it) */
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
                className="w-full px-3 py-2 bg-input-bg text-text-primary rounded-[var(--radius-lg)] border border-input-border focus:outline-none focus:border-action/50"
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

          {/* Description */}
          <div>
            <label className="block text-sm text-text-tertiary mb-1">Description (optional)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Working on user authentication"
              className="w-full px-3 py-2 bg-input-bg text-text-primary rounded-[var(--radius-lg)] border border-input-border focus:outline-none focus:border-action/50"
            />
          </div>

          <AgentProviderSelect
            agentProviders={agentProviders}
            agentProvider={agentProvider}
            defaultAgent={defaultAgent}
            onAgentProviderChange={setAgentProvider}
          />

          {/* Tab Visibility */}
          <div>
            <label className="flex items-center gap-2 text-sm text-text-tertiary">
              <input
                type="checkbox"
                checked={customizeTabs}
                onChange={() => {
                  if (customizeTabs) {
                    setTabVisibility(globalTabVisibility)
                  }
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

          {error && <div className="text-danger text-sm">{error}</div>}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-text-tertiary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <Button
              type="submit"
              disabled={isCreating || !isValid()}
              data-testid="create-session-submit"
              variant="primary"
            >
              {isCreating ? 'Creating...' : 'Create Session'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
