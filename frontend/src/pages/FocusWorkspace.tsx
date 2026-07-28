import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Task } from '../types/focus'
import { generateId, todayISO } from '../utils/focus'
import { getApiBase } from '../config'

// Contexts
import { TaskProvider, useTasks } from '../contexts/FocusTaskContext'

// Hooks
import { useTheme } from '../hooks/useTheme'
import { useFilters } from '../hooks/useFilters'
import { useNotes } from '../hooks/useNotes'
import { useArchive } from '../hooks/useArchive'
import { useDragDrop } from '../hooks/useDragDrop'
import { useTouchDrag } from '../hooks/useTouchDrag'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { useClickOutside } from '../hooks/useClickOutside'
import { useLocalStorage } from '../hooks/useLocalStorage'
import { useSessionStatus } from '../hooks/useSessionStatus'
import { useWorktrees, type RawSession, type Worktree } from '../hooks/useWorktrees'
import { useAttentionItems } from '../hooks/useAttentionItems'
import { useAvailableRepos } from '../hooks/useAvailableRepos'

// Utils
import { deriveRepos, type Repo } from '../utils/repos'
import { resolveBoardStatus } from '../utils/statusMigration'

// Components
import NotesBar from '../components/focus/NotesBar'
import Inbox from '../components/focus/Inbox'
import AttentionStrip from '../components/focus/AttentionStrip'
import WorktreePanel from '../components/focus/WorktreePanel'
import Toolbar from '../components/focus/Toolbar'
import RepoLane from '../components/focus/RepoLane'
import TaskBoard from '../components/focus/TaskBoard'
import TaskModal from '../components/focus/TaskModal'
import type { LaunchAgentChoice } from '../components/focus/LaunchAgentForm'
import FocusCreateSessionModal from '../components/focus/create-session/FocusCreateSessionModal'
import ArchiveModal from '../components/focus/ArchiveModal'
import FilterDropdown from '../components/focus/FilterDropdown'
import ShortcutOverlay from '../components/focus/ShortcutOverlay'
import Toast from '../components/focus/Toast'
import MobileActionBar from '../components/focus/MobileActionBar'
import ConfirmDialog from '../components/focus/ConfirmDialog'
import SessionPicker from '../components/focus/SessionPicker'
import TopNav from '../components/TopNav'

// Grace period after sending a "close out" prompt during which we ignore idle
// state reads — the backend's own idle detector has hysteresis but we still
// need a moment for the agent to start typing before its idle state can be
// trusted (see idle_detector.py: STATE_CHANGE_DELAY_MS/LEAVE_WORKING_DELAY_MS).
const CLOSE_OUT_GRACE_MS = 3000

function toSlug(text: string): string {
  return (
    text
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s_-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '') || 'session'
  )
}

/**
 * The repo path to branch a new worktree from: prefer an already-known main
 * worktree (from a linked session), falling back to the repo's own path when
 * it was matched against a configured search directory — so launching works
 * even for a repo with no sessions linked yet.
 */
function resolveParentRepoPath(
  task: Task,
  repos: Repo[],
  worktreesByRepo: Record<string, Worktree[]>
): string | undefined {
  const repoWorktrees = task.project ? worktreesByRepo[task.project] || [] : []
  const mainWorktree = repoWorktrees.find((w) => w.is_main)
  const repo = task.project ? repos.find((r) => r.id === task.project) : undefined
  return mainWorktree?.path || repo?.path
}

// ---------------------------------------------------------------------------
// Inner component (needs to be inside TaskProvider)
// ---------------------------------------------------------------------------

function FocusWorkspaceInner() {
  const navigate = useNavigate()

  // -------------------------------------------------------------------------
  // Task context
  // -------------------------------------------------------------------------
  const {
    tasks,
    setTasks,
    addTask,
    updateTask,
    deleteTask,
    moveTaskToStatus,
    markChanged,
    modalOpenRef,
    showToast,
    toastMessage,
    toastVisible,
  } = useTasks()

  // -------------------------------------------------------------------------
  // Hooks
  // -------------------------------------------------------------------------
  const { theme, setTheme } = useTheme()
  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }, [theme, setTheme])

  const filters = useFilters()
  const { notesContent, setNotesContent, notesOpen, setNotesOpen } = useNotes()
  const { archiveData, loading: archiveLoading, openArchive, archiveDoneTasks } = useArchive()
  const { getDragHandlers, getDropZoneHandlers } = useDragDrop()

  // Repos derived from tasks' project field, merged with the actual repos found
  // under the configured search directories (same source as the create-session picker).
  const availableRepos = useAvailableRepos()
  const repos = useMemo(() => deriveRepos(tasks, availableRepos), [tasks, availableRepos])

  // Raw sessions (fetched once, polled) — feeds useWorktrees + WorktreePanel
  const [sessions, setSessions] = useState<RawSession[]>([])
  useEffect(() => {
    let cancelled = false
    async function fetchSessions() {
      try {
        const res = await fetch(`${getApiBase()}/sessions`)
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) setSessions(data.sessions || data || [])
      } catch {
        /* ignore — leave previous sessions list in place */
      }
    }
    fetchSessions()
    const interval = setInterval(fetchSessions, 3000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const {
    worktreesByRepo,
    repoPathErrors,
    refetch: refetchWorktrees,
  } = useWorktrees(repos, tasks, sessions)

  // Session status polling
  const sessionNames = useMemo(
    () => tasks.filter((t) => t.session_name).map((t) => t.session_name),
    [tasks]
  )
  const sessionStatusMap = useSessionStatus(sessionNames)

  const attentionItems = useAttentionItems(tasks, sessionStatusMap)

  // Branch lookup per task (via linked session's worktreeBranch), keyed by task.id
  const worktreeBranchByTaskId = useMemo(() => {
    const map: Record<string, string | undefined> = {}
    for (const task of tasks) {
      if (!task.session_name) continue
      const session = sessions.find((s) => s.name === task.session_name)
      map[task.id] = session?.worktreeBranch || undefined
    }
    return map
  }, [tasks, sessions])

  // sessionStatusMap is keyed by session name; re-key by task.id for board/lane components
  const sessionStatusByTaskId = useMemo(() => {
    const map: typeof sessionStatusMap = {}
    for (const task of tasks) {
      if (task.session_name && sessionStatusMap[task.session_name]) {
        map[task.id] = sessionStatusMap[task.session_name]
      }
    }
    return map
  }, [tasks, sessionStatusMap])

  // -------------------------------------------------------------------------
  // UI state
  // -------------------------------------------------------------------------
  const [showArchiveModal, setShowArchiveModal] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [newTaskStatus, setNewTaskStatus] = useState<string | null>(null)
  const [newTaskProject, setNewTaskProject] = useState<string | undefined>(undefined)
  const [sessionTask, setSessionTask] = useState<Task | null>(null)
  const [inboxOpen, setInboxOpen] = useState(false)
  const [backlogCollapsed, setBacklogCollapsed] = useLocalStorage('backlogCollapsed', true)
  const [doneCollapsed, setDoneCollapsed] = useLocalStorage('doneCollapsed', true)
  const [groupByRepo, setGroupByRepo] = useLocalStorage('lumbergh:focus:groupByRepo', true)
  const [worktreePanelOpen, setWorktreePanelOpen] = useLocalStorage(
    'lumbergh:focus:worktreePanelOpen',
    false
  )
  const [pickerTask, setPickerTask] = useState<Task | null>(null)
  const [confirmDialog, setConfirmDialog] = useState<{
    message: string
    onConfirm: () => void
  } | null>(null)

  // Worktree close-out state machine (owned here per WorktreePanel's doc comment)
  const [closingWorktreePaths, setClosingWorktreePaths] = useState<Set<string>>(new Set())
  const [mergedWorktreePaths, setMergedWorktreePaths] = useState<Set<string>>(new Set())

  // Filter dropdown state
  const [projectFilterOpen, setProjectFilterOpen] = useState(false)
  const [priorityFilterOpen, setPriorityFilterOpen] = useState(false)

  const projectFilterRef = useRef<HTMLDivElement>(null)
  const priorityFilterRef = useRef<HTMLDivElement>(null)
  const inboxInputRef = useRef<HTMLInputElement>(null)
  const boardSectionRef = useRef<HTMLDivElement>(null)

  // Close filter dropdowns when clicking outside
  useClickOutside(
    projectFilterRef,
    projectFilterOpen,
    useCallback(() => setProjectFilterOpen(false), [])
  )
  useClickOutside(
    priorityFilterRef,
    priorityFilterOpen,
    useCallback(() => setPriorityFilterOpen(false), [])
  )

  // -------------------------------------------------------------------------
  // Sync modalOpenRef — tells polling to skip when a modal is open
  // -------------------------------------------------------------------------
  useEffect(() => {
    modalOpenRef.current =
      editingTask !== null ||
      newTaskStatus !== null ||
      sessionTask !== null ||
      pickerTask !== null ||
      showArchiveModal ||
      showShortcuts
  }, [
    editingTask,
    newTaskStatus,
    sessionTask,
    pickerTask,
    showArchiveModal,
    showShortcuts,
    modalOpenRef,
  ])

  // -------------------------------------------------------------------------
  // Touch DnD
  // -------------------------------------------------------------------------
  useTouchDrag({
    onMoveTask: useCallback(
      (taskId: string, newStatus: string, beforeTaskId: string | null) => {
        moveTaskToStatus(taskId, newStatus, beforeTaskId)
      },
      [moveTaskToStatus]
    ),
    onReorderSwimlane: useCallback(() => {}, []),
  })

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  // -------------------------------------------------------------------------
  useKeyboardShortcuts(
    useMemo(
      () => ({
        onNewInbox: () => {
          setInboxOpen(true)
          inboxInputRef.current?.focus()
        },
        onToggleTheme: toggleTheme,
        onShowHelp: () => setShowShortcuts((prev) => !prev),
        onEscape: () => {
          if (showShortcuts) {
            setShowShortcuts(false)
          } else if (editingTask !== null || newTaskStatus !== null) {
            setEditingTask(null)
            setNewTaskStatus(null)
          } else if (pickerTask !== null) {
            setPickerTask(null)
          } else if (sessionTask !== null) {
            setSessionTask(null)
          } else if (showArchiveModal) {
            setShowArchiveModal(false)
          } else if (projectFilterOpen) {
            setProjectFilterOpen(false)
          } else if (priorityFilterOpen) {
            setPriorityFilterOpen(false)
          } else {
            ;(document.activeElement as HTMLElement)?.blur?.()
          }
        },
      }),
      [
        toggleTheme,
        showShortcuts,
        editingTask,
        newTaskStatus,
        pickerTask,
        sessionTask,
        showArchiveModal,
        projectFilterOpen,
        priorityFilterOpen,
      ]
    )
  )

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------
  const uniqueProjects = useMemo(() => filters.getUniqueProjects(tasks), [tasks, filters])

  // -------------------------------------------------------------------------
  // Handler: edit / add task modal
  // -------------------------------------------------------------------------
  const handleEditTask = useCallback((task: Task) => {
    setEditingTask(task)
    setNewTaskStatus(null)
    setNewTaskProject(undefined)
  }, [])

  const handleViewSession = useCallback(
    (task: Task) => {
      if (task.session_name) navigate('/session/' + task.session_name)
    },
    [navigate]
  )

  const handleAddTask = useCallback((status: string) => {
    setEditingTask(null)
    setNewTaskStatus(status)
    setNewTaskProject(undefined)
  }, [])

  /** Used by RepoLane's per-repo "+ Task" button — opens the modal pre-filled with that repo. */
  const handleAddTaskForRepo = useCallback((repoId: string) => {
    setEditingTask(null)
    setNewTaskStatus('backlog')
    setNewTaskProject(repoId)
  }, [])

  const handleSaveTask = useCallback(
    (data: Partial<Task> & { title: string }) => {
      if (editingTask) {
        const updates: Partial<Task> = { ...data }
        if (updates.status === 'done') {
          updates.completed = true
          updates.completed_date = editingTask.completed_date || todayISO()
        } else {
          updates.completed = false
          updates.completed_date = ''
        }
        updateTask(editingTask.id, updates)
      } else {
        const newTask: Task = {
          id: generateId(),
          title: data.title,
          project: data.project || '',
          priority: data.priority || 'med',
          status: data.status || newTaskStatus || 'backlog',
          blocker: data.blocker || '',
          check_in_note: data.check_in_note || '',
          completed: data.status === 'done' || false,
          completed_date: data.status === 'done' ? todayISO() : '',
          session_name: '',
          session_status: '',
          subtasks: data.subtasks || [],
        }
        addTask(newTask)
      }
      setEditingTask(null)
      setNewTaskStatus(null)
      setNewTaskProject(undefined)
    },
    [editingTask, newTaskStatus, addTask, updateTask]
  )

  const handleDeleteTask = useCallback(() => {
    if (editingTask) {
      deleteTask(editingTask.id)
    }
    setEditingTask(null)
    setNewTaskStatus(null)
    setNewTaskProject(undefined)
  }, [editingTask, deleteTask])

  const handleCloseTaskModal = useCallback(() => {
    setEditingTask(null)
    setNewTaskStatus(null)
    setNewTaskProject(undefined)
  }, [])

  // -------------------------------------------------------------------------
  // Handler: Session picker + linking
  // -------------------------------------------------------------------------
  const linkedSessionNames = useMemo(
    () => tasks.filter((t) => t.session_name && t.id !== pickerTask?.id).map((t) => t.session_name),
    [tasks, pickerTask]
  )

  const handleOpenSessionPicker = useCallback((task: Task) => {
    setPickerTask(task)
  }, [])

  const handleLinkSession = useCallback(
    (sessionName: string) => {
      if (!pickerTask) return
      updateTask(pickerTask.id, { session_name: sessionName })
      setPickerTask(null)
      showToast('Session linked: ' + sessionName)
    },
    [pickerTask, updateTask, showToast]
  )

  const handleCreateNewFromPicker = useCallback(() => {
    setSessionTask(pickerTask)
    setPickerTask(null)
  }, [pickerTask])

  const handleSessionCreated = useCallback(
    (sessionName: string) => {
      if (!sessionTask) return
      updateTask(sessionTask.id, { session_name: sessionName })
      setSessionTask(null)
      showToast('Session created: ' + sessionName)
      navigate('/session/' + sessionName)
    },
    [sessionTask, updateTask, showToast, navigate]
  )

  // -------------------------------------------------------------------------
  // Handler: Inbox
  // -------------------------------------------------------------------------
  const handleInboxAdd = useCallback(
    (title: string) => {
      const newTask: Task = {
        id: generateId(),
        title,
        project: '',
        priority: 'med',
        status: 'inbox',
        blocker: '',
        check_in_note: '',
        completed: false,
        completed_date: '',
        session_name: '',
        session_status: '',
        subtasks: [],
      }
      addTask(newTask)
    },
    [addTask]
  )

  const handleInboxUpdateTitle = useCallback(
    (taskId: string, newTitle: string) => {
      updateTask(taskId, { title: newTitle })
    },
    [updateTask]
  )

  const handlePromoteToBacklog = useCallback(
    (taskId: string, repoId: string) => {
      updateTask(taskId, { project: repoId, status: 'backlog' })
    },
    [updateTask]
  )

  // -------------------------------------------------------------------------
  // Handler: Archive
  // -------------------------------------------------------------------------
  const handleOpenArchive = useCallback(async () => {
    await openArchive()
    setShowArchiveModal(true)
  }, [openArchive])

  // Listen for archive event from AppHeader
  useEffect(() => {
    const handler = () => {
      handleOpenArchive()
    }
    window.addEventListener('lumbergh:open-archive', handler)
    return () => window.removeEventListener('lumbergh:open-archive', handler)
  }, [handleOpenArchive])

  const handleArchiveDone = useCallback(
    (repoId?: string) => {
      const scoped = repoId ? tasks.filter((t) => t.project === repoId) : tasks
      const doneTasks = scoped.filter((t) => resolveBoardStatus(t) === 'done')
      if (!doneTasks.length) return
      setConfirmDialog({
        message: `Archive ${doneTasks.length} done task${doneTasks.length > 1 ? 's' : ''}?`,
        onConfirm: async () => {
          setConfirmDialog(null)
          const doneIds = new Set(doneTasks.map((t) => t.id))
          const msg = await archiveDoneTasks(scoped, () => {
            setTasks((prev) => prev.filter((t) => !doneIds.has(t.id)))
            markChanged()
          })
          if (msg) showToast(msg)
        },
      })
    },
    [tasks, archiveDoneTasks, setTasks, markChanged, showToast]
  )

  const handleToggleBacklogCollapsed = useCallback(
    () => setBacklogCollapsed(!backlogCollapsed),
    [backlogCollapsed, setBacklogCollapsed]
  )
  const handleToggleDoneCollapsed = useCallback(
    () => setDoneCollapsed(!doneCollapsed),
    [doneCollapsed, setDoneCollapsed]
  )

  // -------------------------------------------------------------------------
  // Handler: Board drop
  // -------------------------------------------------------------------------
  const handleDropTask = useCallback(
    (taskId: string, status: string, beforeTaskId: string | null) => {
      moveTaskToStatus(taskId, status, beforeTaskId)
    },
    [moveTaskToStatus]
  )

  // -------------------------------------------------------------------------
  // Handler: Launch agent — creates a session (new worktree or existing one)
  // and links it to the task.
  // -------------------------------------------------------------------------
  const handleLaunchAgent = useCallback(
    async (taskId: string, choice: LaunchAgentChoice) => {
      const task = tasks.find((t) => t.id === taskId)
      if (!task) return

      try {
        let body: Record<string, unknown>

        if (choice.worktreePath) {
          // Launch directly into an already-existing worktree directory.
          body = {
            name: `${toSlug(task.title)}-${generateId().slice(0, 5)}`,
            description: task.title,
            mode: 'direct',
            workdir: choice.worktreePath,
          }
        } else if (choice.newBranch) {
          const parentRepoPath = resolveParentRepoPath(task, repos, worktreesByRepo)
          if (!parentRepoPath) {
            const pathError = task.project ? repoPathErrors[task.project] : undefined
            showToast(
              pathError
                ? `Cannot resolve repo path: ${pathError}`
                : 'Cannot resolve repo path — link an existing session in this repo first'
            )
            return
          }
          body = {
            name: `${toSlug(choice.newBranch)}-${generateId().slice(0, 5)}`,
            description: task.title,
            mode: 'worktree',
            worktree: {
              parent_repo: parentRepoPath,
              branch: choice.newBranch,
              create_branch: true,
            },
          }
        } else {
          return
        }

        const res = await fetch(`${getApiBase()}/sessions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || 'Failed to create session')
        }
        const data = await res.json()
        updateTask(taskId, { session_name: data.name, status: 'in-progress' })
        showToast('Agent launched: ' + data.name)
        refetchWorktrees()
      } catch (err) {
        showToast(err instanceof Error ? err.message : 'Failed to launch agent')
      }
    },
    [tasks, worktreesByRepo, repoPathErrors, repos, updateTask, showToast, refetchWorktrees]
  )

  // -------------------------------------------------------------------------
  // Handler: Worktree close-out state machine
  // -------------------------------------------------------------------------
  const handleSendWrapup = useCallback(
    (sessionName: string, promptText: string, worktreePath: string) => {
      fetch(`${getApiBase()}/session/${sessionName}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: promptText, send_enter: true }),
      }).catch(() => {
        showToast('Failed to send prompt to agent')
      })

      setClosingWorktreePaths((prev) => new Set(prev).add(worktreePath))

      const sentAt = Date.now()
      const poll = setInterval(async () => {
        if (Date.now() - sentAt < CLOSE_OUT_GRACE_MS) return

        try {
          const res = await fetch(`${getApiBase()}/sessions`)
          if (!res.ok) return
          const data = await res.json()
          const liveSessions: RawSession[] = data.sessions || data || []
          const session = liveSessions.find((s) => s.name === sessionName)
          if (!session) return
          if (session.idleState && session.idleState !== 'working') {
            clearInterval(poll)
            setClosingWorktreePaths((prev) => {
              const next = new Set(prev)
              next.delete(worktreePath)
              return next
            })
            setMergedWorktreePaths((prev) => new Set(prev).add(worktreePath))
            const linkedTask = tasks.find((t) => t.session_name === sessionName)
            if (linkedTask) {
              updateTask(linkedTask.id, { status: 'done' })
            }
          }
        } catch {
          /* ignore poll errors, try again next tick */
        }
      }, 1500)
    },
    [tasks, updateTask, showToast]
  )

  const handleCleanupWorktree = useCallback(
    async (repoPath: string, worktreePath: string) => {
      try {
        const url = `${getApiBase()}/sessions/worktrees?repo_path=${encodeURIComponent(repoPath)}&worktree_path=${encodeURIComponent(worktreePath)}`
        const res = await fetch(url, { method: 'DELETE' })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || 'Failed to remove worktree')
        }
        setMergedWorktreePaths((prev) => {
          const next = new Set(prev)
          next.delete(worktreePath)
          return next
        })
        showToast('Worktree removed')
        refetchWorktrees()
      } catch (err) {
        showToast(err instanceof Error ? err.message : 'Failed to remove worktree')
      }
    },
    [showToast, refetchWorktrees]
  )

  // -------------------------------------------------------------------------
  // Filter dropdown items
  // -------------------------------------------------------------------------
  const priorityItems = useMemo(
    () => [
      { key: 'high', label: 'High', selected: filters.priorityFilters.high },
      { key: 'med', label: 'Med', selected: filters.priorityFilters.med },
      { key: 'low', label: 'Low', selected: filters.priorityFilters.low },
    ],
    [filters.priorityFilters]
  )

  const priorityActiveCount = useMemo(
    () => priorityItems.filter((i) => i.selected).length,
    [priorityItems]
  )

  const projectItems = useMemo(() => {
    const items = uniqueProjects.map((p) => ({
      key: p,
      label: p,
      selected: filters.projectFilters.has(p),
    }))
    items.push({
      key: '__none__',
      label: '(No project)',
      selected: filters.projectFilters.has('__none__'),
    })
    return items
  }, [uniqueProjects, filters.projectFilters])

  const projectActiveCount = useMemo(() => filters.projectFilters.size, [filters.projectFilters])

  // -------------------------------------------------------------------------
  // Filter dropdown toggle handlers (mutually exclusive)
  // -------------------------------------------------------------------------
  const handleToggleProjectFilter = useCallback(() => {
    setProjectFilterOpen((prev) => !prev)
    setPriorityFilterOpen(false)
  }, [])

  const handleTogglePriorityFilter = useCallback(() => {
    setPriorityFilterOpen((prev) => !prev)
    setProjectFilterOpen(false)
  }, [])

  const handleTogglePriorityItem = useCallback(
    (key: string) => {
      filters.togglePriority(key as 'high' | 'med' | 'low')
    },
    [filters]
  )

  // -------------------------------------------------------------------------
  // Filter dropdowns JSX (passed to Toolbar)
  // -------------------------------------------------------------------------
  const filterDropdowns = useMemo(
    () => (
      <>
        <div ref={projectFilterRef}>
          <FilterDropdown
            id="projectFilterWrap"
            buttonId="projectFilterBtn"
            menuId="projectFilterMenu"
            label="Project"
            items={projectItems}
            activeCount={projectActiveCount}
            totalCount={projectItems.length}
            onToggleItem={filters.toggleProject}
            onClearAll={filters.clearProjectFilters}
            isOpen={projectFilterOpen}
            onToggleOpen={handleToggleProjectFilter}
          />
        </div>
        <div ref={priorityFilterRef}>
          <FilterDropdown
            id="priorityFilterWrap"
            buttonId="priorityFilterBtn"
            menuId="priorityFilterMenu"
            label="Priority"
            items={priorityItems}
            activeCount={priorityActiveCount}
            totalCount={3}
            onToggleItem={handleTogglePriorityItem}
            isOpen={priorityFilterOpen}
            onToggleOpen={handleTogglePriorityFilter}
          />
        </div>
      </>
    ),
    [
      projectItems,
      projectActiveCount,
      projectFilterOpen,
      filters.toggleProject,
      filters.clearProjectFilters,
      handleToggleProjectFilter,
      priorityItems,
      priorityActiveCount,
      priorityFilterOpen,
      handleTogglePriorityItem,
      handleTogglePriorityFilter,
    ]
  )

  // -------------------------------------------------------------------------
  // Worktree count (for Toolbar's "Worktrees (N)" toggle)
  // -------------------------------------------------------------------------
  const worktreeCount = useMemo(
    () => repos.reduce((sum, repo) => sum + (worktreesByRepo[repo.id]?.length || 0), 0),
    [repos, worktreesByRepo]
  )

  // -------------------------------------------------------------------------
  // Worktree branch for the task currently open in the modal (read-only display)
  // -------------------------------------------------------------------------
  const editingTaskWorktreeBranch = editingTask ? worktreeBranchByTaskId[editingTask.id] : undefined

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className="focus-view flex flex-col h-full bg-bg-sunken text-text-primary overflow-hidden">
      <header
        className="glass flex items-center justify-between p-4 border-b border-border-default shrink-0"
        style={{ paddingTop: 'max(1rem, env(safe-area-inset-top))' }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-text-secondary">Lumbergh</h1>
          <TopNav active="workspace" />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="w-8 h-8 rounded-[var(--radius-md)] bg-control-bg hover:bg-control-bg-hover flex items-center justify-center text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </div>
      </header>

      <div className="main-content flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-5">
        <AttentionStrip
          attentionItems={attentionItems}
          sessionStatusMap={sessionStatusMap}
          worktreeBranches={worktreeBranchByTaskId as Record<string, string>}
          onViewSession={handleViewSession}
        />

        <Inbox
          tasks={tasks}
          repos={repos}
          isOpen={inboxOpen}
          onToggleOpen={useCallback(() => setInboxOpen((prev) => !prev), [])}
          onAddTask={handleInboxAdd}
          onEditTask={handleEditTask}
          onUpdateTitle={handleInboxUpdateTitle}
          onPromoteToBacklog={handlePromoteToBacklog}
          getDragHandlers={getDragHandlers}
          dropZoneHandlers={useMemo(
            () => getDropZoneHandlers((taskId: string) => moveTaskToStatus(taskId, 'inbox')),
            [getDropZoneHandlers, moveTaskToStatus]
          )}
          inputRef={inboxInputRef}
        />

        <NotesBar
          content={notesContent}
          onChange={setNotesContent}
          isOpen={notesOpen}
          onToggleOpen={useCallback(() => setNotesOpen(!notesOpen), [notesOpen, setNotesOpen])}
        />

        <Toolbar
          groupByRepo={groupByRepo}
          onSetGroupByRepo={setGroupByRepo}
          worktreeCount={worktreeCount}
          worktreePanelOpen={worktreePanelOpen}
          onToggleWorktreePanel={useCallback(
            () => setWorktreePanelOpen(!worktreePanelOpen),
            [worktreePanelOpen, setWorktreePanelOpen]
          )}
          onAddTask={useCallback(() => handleAddTask('backlog'), [handleAddTask])}
          onOpenArchive={handleOpenArchive}
          filterDropdowns={filterDropdowns}
        />

        <WorktreePanel
          isOpen={worktreePanelOpen}
          onToggleOpen={useCallback(
            () => setWorktreePanelOpen(!worktreePanelOpen),
            [worktreePanelOpen, setWorktreePanelOpen]
          )}
          repos={repos}
          worktreesByRepo={worktreesByRepo}
          tasks={tasks}
          sessions={sessions}
          closingWorktreePaths={closingWorktreePaths}
          mergedWorktreePaths={mergedWorktreePaths}
          onCleanupWorktree={handleCleanupWorktree}
          onSendWrapup={handleSendWrapup}
          onViewTask={handleEditTask}
        />

        {groupByRepo ? (
          <RepoLane
            repos={repos}
            tasks={tasks}
            worktreesByRepo={worktreesByRepo}
            worktreeBranchByTaskId={worktreeBranchByTaskId}
            sessionStatusByTaskId={sessionStatusByTaskId}
            onEditTask={handleEditTask}
            onAddTask={handleAddTaskForRepo}
            onArchiveDone={handleArchiveDone}
            onDropTask={handleDropTask}
            getDragHandlers={getDragHandlers}
            onLaunchAgent={handleLaunchAgent}
            onOpenSessionPicker={handleOpenSessionPicker}
            onViewSession={handleViewSession}
            taskMatchesFilters={filters.taskMatchesFilters}
          />
        ) : (
          <TaskBoard
            tasks={tasks}
            backlogCollapsed={backlogCollapsed}
            onToggleBacklogCollapsed={handleToggleBacklogCollapsed}
            doneCollapsed={doneCollapsed}
            onToggleDoneCollapsed={handleToggleDoneCollapsed}
            onEditTask={handleEditTask}
            onAddTask={handleAddTask}
            onArchiveDone={handleArchiveDone}
            onDropTask={handleDropTask}
            getDragHandlers={getDragHandlers}
            taskMatchesFilters={filters.taskMatchesFilters}
            worktreeBranchByTaskId={worktreeBranchByTaskId}
            sessionStatusByTaskId={sessionStatusByTaskId}
            onLaunchAgent={handleLaunchAgent}
            onOpenSessionPicker={handleOpenSessionPicker}
            onViewSession={handleViewSession}
            boardRef={boardSectionRef}
          />
        )}
      </div>

      <TaskModal
        isOpen={editingTask !== null || newTaskStatus !== null}
        task={editingTask}
        defaultStatus={newTaskStatus || 'backlog'}
        defaultProject={newTaskProject}
        repos={repos}
        worktreeBranch={editingTaskWorktreeBranch}
        onSave={handleSaveTask}
        onDelete={handleDeleteTask}
        onClose={handleCloseTaskModal}
      />

      <FocusCreateSessionModal
        isOpen={sessionTask !== null}
        task={sessionTask}
        onClose={useCallback(() => setSessionTask(null), [])}
        onSessionCreated={handleSessionCreated}
      />

      <SessionPicker
        isOpen={pickerTask !== null}
        onClose={useCallback(() => setPickerTask(null), [])}
        linkedSessionNames={linkedSessionNames}
        onLinkSession={handleLinkSession}
        onCreateNew={handleCreateNewFromPicker}
      />

      <ArchiveModal
        isOpen={showArchiveModal}
        data={archiveData}
        loading={archiveLoading}
        onClose={useCallback(() => setShowArchiveModal(false), [])}
      />

      <ShortcutOverlay
        isOpen={showShortcuts}
        onClose={useCallback(() => setShowShortcuts(false), [])}
      />

      <Toast message={toastMessage} visible={toastVisible} />

      <ConfirmDialog
        isOpen={!!confirmDialog}
        message={confirmDialog?.message ?? ''}
        onConfirm={confirmDialog?.onConfirm ?? (() => {})}
        onCancel={() => setConfirmDialog(null)}
      />

      <MobileActionBar
        onAddToday={useCallback(() => handleAddTask('backlog'), [handleAddTask])}
        onAddInbox={useCallback(() => handleAddTask('inbox'), [handleAddTask])}
        onScrollToBoard={useCallback(() => {
          boardSectionRef.current?.scrollIntoView({ behavior: 'smooth' })
        }, [])}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page export — wraps inner component with FocusTaskContext provider
// ---------------------------------------------------------------------------

export default function FocusWorkspace() {
  return (
    <TaskProvider>
      <FocusWorkspaceInner />
    </TaskProvider>
  )
}
