import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Task } from '../types/focus'
import { generateId, todayISO } from '../utils/focus'

// Contexts
import { TaskProvider, useTasks } from '../contexts/FocusTaskContext'

// Hooks
import { useTheme } from '../hooks/useTheme'
import { usePomodoro } from '../hooks/usePomodoro'
import { useFilters } from '../hooks/useFilters'
import { useNotes } from '../hooks/useNotes'
import { useArchive } from '../hooks/useArchive'
import { useDragDrop } from '../hooks/useDragDrop'
import { useTouchDrag } from '../hooks/useTouchDrag'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { useClickOutside } from '../hooks/useClickOutside'
import { useLocalStorage } from '../hooks/useLocalStorage'
import { useSessionStatus } from '../hooks/useSessionStatus'

// Components
import Topbar from '../components/focus/Topbar'
import TodayPanel from '../components/focus/TodayPanel'
import InFlightPanel from '../components/focus/InFlightPanel'
import NotesBar from '../components/focus/NotesBar'
import Inbox from '../components/focus/Inbox'
import TaskBoard from '../components/focus/TaskBoard'
import TaskModal from '../components/focus/TaskModal'
import FocusCreateSessionModal from '../components/focus/create-session/FocusCreateSessionModal'
import ArchiveModal from '../components/focus/ArchiveModal'
import FilterDropdown from '../components/focus/FilterDropdown'
import ShortcutOverlay from '../components/focus/ShortcutOverlay'
import Toast from '../components/focus/Toast'
import MobileActionBar from '../components/focus/MobileActionBar'
import ConfirmDialog from '../components/focus/ConfirmDialog'

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

  const { pomo, pomoStart, pomoPause, pomoResume, pomoStop } = usePomodoro()
  const filters = useFilters()
  const { notesContent, setNotesContent, notesOpen, setNotesOpen } = useNotes()
  const { archiveData, loading: archiveLoading, openArchive, archiveDoneTasks } = useArchive()
  const { getDragHandlers, getDropZoneHandlers } = useDragDrop()

  // Session status polling
  const sessionNames = useMemo(
    () => tasks.filter((t) => t.session_name).map((t) => t.session_name),
    [tasks]
  )
  const sessionStatusMap = useSessionStatus(sessionNames)

  // -------------------------------------------------------------------------
  // UI state
  // -------------------------------------------------------------------------
  const [showArchiveModal, setShowArchiveModal] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [newTaskStatus, setNewTaskStatus] = useState<string | null>(null)
  const [sessionTask, setSessionTask] = useState<Task | null>(null)
  const [inboxOpen, setInboxOpen] = useState(false)
  const [boardCollapsed, setBoardCollapsed] = useState(false)
  const [backlogCollapsed, setBacklogCollapsed] = useLocalStorage('backlogCollapsed', true)
  const [doneCollapsed, setDoneCollapsed] = useLocalStorage('doneCollapsed', true)
  const [swimlaneMode, setSwimlaneMode] = useState(false)
  const [swimlaneOrder, setSwimlaneOrder] = useLocalStorage<string[]>('swimlaneOrder', [])
  const [confirmDialog, setConfirmDialog] = useState<{
    message: string
    onConfirm: () => void
  } | null>(null)

  // Filter dropdown state
  const [projectFilterOpen, setProjectFilterOpen] = useState(false)
  const [priorityFilterOpen, setPriorityFilterOpen] = useState(false)

  const projectFilterRef = useRef<HTMLDivElement>(null)
  const priorityFilterRef = useRef<HTMLDivElement>(null)
  const inboxInputRef = useRef<HTMLInputElement>(null)
  const todayPanelRef = useRef<HTMLDivElement>(null)
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
      showArchiveModal ||
      showShortcuts
  }, [editingTask, newTaskStatus, sessionTask, showArchiveModal, showShortcuts, modalOpenRef])

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
    onReorderSwimlane: useCallback(
      (source: string, target: string) => {
        const order = [...swimlaneOrder]
        const si = order.indexOf(source)
        const ti = order.indexOf(target)
        if (si === -1 || ti === -1) return
        order.splice(si, 1)
        order.splice(ti, 0, source)
        setSwimlaneOrder(order)
      },
      [swimlaneOrder, setSwimlaneOrder]
    ),
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
        onFocusToday: () => {
          todayPanelRef.current?.scrollIntoView({ behavior: 'smooth' })
        },
        onToggleTheme: toggleTheme,
        onShowHelp: () => setShowShortcuts((prev) => !prev),
        onEscape: () => {
          if (showShortcuts) {
            setShowShortcuts(false)
          } else if (editingTask !== null || newTaskStatus !== null) {
            setEditingTask(null)
            setNewTaskStatus(null)
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
        sessionTask,
        showArchiveModal,
        projectFilterOpen,
        priorityFilterOpen,
      ]
    )
  )

  // -------------------------------------------------------------------------
  // Pomodoro auto-stop: if pomo task is no longer "today", stop
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!pomo.active || !pomo.taskId) return
    const task = tasks.find((t) => t.id === pomo.taskId)
    if (!task || task.status !== 'today') {
      pomoStop()
    }
  }, [tasks, pomo.active, pomo.taskId, pomoStop])

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
  }, [])

  const handleAddTask = useCallback((status: string) => {
    setEditingTask(null)
    setNewTaskStatus(status)
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
          status: data.status || newTaskStatus || 'today',
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
    },
    [editingTask, newTaskStatus, addTask, updateTask]
  )

  const handleDeleteTask = useCallback(() => {
    if (editingTask) {
      deleteTask(editingTask.id)
    }
    setEditingTask(null)
    setNewTaskStatus(null)
  }, [editingTask, deleteTask])

  const handleCloseTaskModal = useCallback(() => {
    setEditingTask(null)
    setNewTaskStatus(null)
  }, [])

  // -------------------------------------------------------------------------
  // Handler: toggle complete (Today card)
  // -------------------------------------------------------------------------
  const handleToggleComplete = useCallback(
    (taskId: string) => {
      const task = tasks.find((t) => t.id === taskId)
      if (!task) return
      if (task.completed) {
        updateTask(taskId, { completed: false, status: 'today', completed_date: '' })
      } else {
        updateTask(taskId, { completed: true, status: 'done', completed_date: todayISO() })
      }
    },
    [tasks, updateTask]
  )

  // -------------------------------------------------------------------------
  // Handler: Pomodoro
  // -------------------------------------------------------------------------
  const handleStartPomo = useCallback(
    (taskId: string) => {
      pomoStart(taskId, tasks)
    },
    [pomoStart, tasks]
  )

  // -------------------------------------------------------------------------
  // Handler: Session
  // -------------------------------------------------------------------------
  const handleLaunchSession = useCallback((task: Task) => {
    setSessionTask(task)
  }, [])

  const handleSessionCreated = useCallback(
    (sessionName: string) => {
      if (!sessionTask) return
      updateTask(sessionTask.id, { session_name: sessionName, session_status: 'working' })
      setSessionTask(null)
      showToast('Session created: ' + sessionName)
      navigate('/session/' + sessionName)
    },
    [sessionTask, updateTask, showToast, navigate]
  )

  const handleDetachSession = useCallback(
    (taskId: string) => {
      updateTask(taskId, { session_name: '', session_status: '' })
      showToast('Session detached')
    },
    [updateTask, showToast]
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

  // -------------------------------------------------------------------------
  // Handler: In Flight check-in note
  // -------------------------------------------------------------------------
  const handleUpdateCheckIn = useCallback(
    (taskId: string, note: string) => {
      updateTask(taskId, { check_in_note: note })
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

  const handleArchiveDone = useCallback(() => {
    const doneTasks = tasks.filter((t) => t.status === 'done')
    if (!doneTasks.length) return
    setConfirmDialog({
      message: `Archive ${doneTasks.length} done task${doneTasks.length > 1 ? 's' : ''}?`,
      onConfirm: async () => {
        setConfirmDialog(null)
        const msg = await archiveDoneTasks(tasks, (newTasks) => {
          setTasks(newTasks)
          markChanged()
        })
        if (msg) showToast(msg)
      },
    })
  }, [tasks, archiveDoneTasks, setTasks, markChanged, showToast])

  // -------------------------------------------------------------------------
  // Handler: Board drop
  // -------------------------------------------------------------------------
  const handleDropTask = useCallback(
    (taskId: string, status: string, beforeTaskId: string | null) => {
      moveTaskToStatus(taskId, status, beforeTaskId)
    },
    [moveTaskToStatus]
  )

  const handleDropSwimlane = useCallback(
    (taskId: string, status: string, project: string) => {
      const task = tasks.find((t) => t.id === taskId)
      if (!task) return
      updateTask(taskId, {
        status,
        project,
        completed: status === 'done',
        completed_date: status === 'done' ? todayISO() : '',
      })
    },
    [tasks, updateTask]
  )

  const handleReorderSwimlane = useCallback(
    (sourceProject: string, targetProject: string) => {
      const order = [...swimlaneOrder]
      const si = order.indexOf(sourceProject)
      const ti = order.indexOf(targetProject)
      if (si === -1 || ti === -1) return
      order.splice(si, 1)
      order.splice(ti, 0, sourceProject)
      setSwimlaneOrder(order)
    },
    [swimlaneOrder, setSwimlaneOrder]
  )

  // -------------------------------------------------------------------------
  // Handler: Promote to today from board
  // -------------------------------------------------------------------------
  const handlePromoteToday = useCallback(
    (taskId: string) => {
      moveTaskToStatus(taskId, 'today')
    },
    [moveTaskToStatus]
  )

  // -------------------------------------------------------------------------
  // Handler: Today panel drop
  // -------------------------------------------------------------------------
  const handleTodayDrop = useCallback(
    (taskId: string, beforeTaskId: string | null) => {
      moveTaskToStatus(taskId, 'today', beforeTaskId)
    },
    [moveTaskToStatus]
  )

  // -------------------------------------------------------------------------
  // In Flight drop zone handlers
  // -------------------------------------------------------------------------
  const inFlightDropHandlers = useMemo(
    () =>
      getDropZoneHandlers((taskId: string) => {
        moveTaskToStatus(taskId, 'running')
      }),
    [getDropZoneHandlers, moveTaskToStatus]
  )

  // Inbox drop zone handlers
  const inboxDropHandlers = useMemo(
    () =>
      getDropZoneHandlers((taskId: string) => {
        moveTaskToStatus(taskId, 'inbox')
      }),
    [getDropZoneHandlers, moveTaskToStatus]
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
  // Filter dropdowns JSX (passed to TaskBoard)
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
  // Drag handlers object for TodayPanel
  // -------------------------------------------------------------------------
  const todayDragHandlers = useMemo(
    () => ({
      getDragHandlers,
      getDropZoneHandlers,
    }),
    [getDragHandlers, getDropZoneHandlers]
  )

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className="focus-view flex flex-col h-full">
      <Topbar pomo={pomo} onPomoPause={pomoPause} onPomoResume={pomoResume} onPomoStop={pomoStop} />

      <div className="main-content flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-5">
        <div className="top-split grid grid-cols-[1fr_1fr] gap-5">
          <TodayPanel
            tasks={tasks}
            pomo={pomo}
            onToggleComplete={handleToggleComplete}
            onStartPomo={handleStartPomo}
            onLaunchSession={handleLaunchSession}
            onEditTask={handleEditTask}
            onAddTask={useCallback(() => handleAddTask('today'), [handleAddTask])}
            onDropTask={handleTodayDrop}
            dragHandlers={todayDragHandlers}
            panelRef={todayPanelRef}
            sessionStatusMap={sessionStatusMap}
            onDetachSession={handleDetachSession}
          />
          <InFlightPanel
            tasks={tasks}
            onEditTask={handleEditTask}
            onLaunchSession={handleLaunchSession}
            onUpdateCheckIn={handleUpdateCheckIn}
            dropZoneHandlers={inFlightDropHandlers}
            getDragHandlers={getDragHandlers}
          />
        </div>

        <NotesBar
          content={notesContent}
          onChange={setNotesContent}
          isOpen={notesOpen}
          onToggleOpen={useCallback(() => setNotesOpen(!notesOpen), [notesOpen, setNotesOpen])}
        />

        <Inbox
          tasks={tasks}
          isOpen={inboxOpen}
          onToggleOpen={useCallback(() => setInboxOpen((prev) => !prev), [])}
          onAddTask={handleInboxAdd}
          onEditTask={handleEditTask}
          onUpdateTitle={handleInboxUpdateTitle}
          getDragHandlers={getDragHandlers}
          dropZoneHandlers={inboxDropHandlers}
          inputRef={inboxInputRef}
        />

        <TaskBoard
          tasks={tasks}
          swimlaneMode={swimlaneMode}
          onToggleSwimlane={useCallback(() => setSwimlaneMode((prev) => !prev), [])}
          boardCollapsed={boardCollapsed}
          onToggleBoardCollapsed={useCallback(() => setBoardCollapsed((prev) => !prev), [])}
          backlogCollapsed={backlogCollapsed}
          onToggleBacklogCollapsed={useCallback(
            () => setBacklogCollapsed(!backlogCollapsed),
            [backlogCollapsed, setBacklogCollapsed]
          )}
          doneCollapsed={doneCollapsed}
          onToggleDoneCollapsed={useCallback(
            () => setDoneCollapsed(!doneCollapsed),
            [doneCollapsed, setDoneCollapsed]
          )}
          onEditTask={handleEditTask}
          onAddTask={handleAddTask}
          onPromoteToday={handlePromoteToday}
          onArchiveDone={handleArchiveDone}
          onDropTask={handleDropTask}
          onDropSwimlane={handleDropSwimlane}
          onReorderSwimlane={handleReorderSwimlane}
          getDragHandlers={getDragHandlers}
          taskMatchesFilters={filters.taskMatchesFilters}
          swimlaneOrder={swimlaneOrder}
          onUpdateSwimlaneOrder={setSwimlaneOrder}
          filterDropdowns={filterDropdowns}
          boardRef={boardSectionRef}
        />
      </div>

      <TaskModal
        isOpen={editingTask !== null || newTaskStatus !== null}
        task={editingTask}
        defaultStatus={newTaskStatus || 'today'}
        projects={uniqueProjects}
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
        onAddToday={useCallback(() => handleAddTask('today'), [handleAddTask])}
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
