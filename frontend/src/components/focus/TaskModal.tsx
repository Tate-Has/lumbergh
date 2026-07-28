import React, { useState, useEffect, useRef, useCallback } from 'react'
import SubtaskEditor from './SubtaskEditor'
import type { Task, SubTask } from '../../types/focus'
import type { Repo } from '../../utils/repos'
import { resolveBoardStatus } from '../../utils/statusMigration'

export interface TaskModalProps {
  isOpen: boolean
  task: Task | null
  defaultStatus: string
  /** Pre-fills the Repo field for a new task (e.g. launched from a specific RepoLane's "+ Task"). */
  defaultProject?: string
  /** Repos derived via deriveRepos(allTasks, availableRepos); used to populate the Repo select. */
  repos: Repo[]
  /**
   * Worktree branch/name for the task's active session, if any. The parent page owns
   * session/worktree lookups (e.g. mapping task.session_name -> branch) and passes the
   * resolved string in here. Undefined/empty means no worktree info to show. Only
   * rendered when task.session_name is set.
   */
  worktreeBranch?: string
  onSave: (data: Partial<Task> & { title: string }) => void
  onDelete: () => void
  onClose: () => void
}

export default function TaskModal({
  isOpen,
  task,
  defaultStatus,
  defaultProject,
  repos,
  worktreeBranch,
  onSave,
  onDelete,
  onClose,
}: TaskModalProps) {
  const [title, setTitle] = useState('')
  const [project, setProject] = useState('')
  const [priority, setPriority] = useState<'high' | 'med' | 'low'>('med')
  const [status, setStatus] = useState('today')
  const [blocker, setBlocker] = useState('')
  const [checkin, setCheckin] = useState('')
  const [subtasks, setSubtasks] = useState<SubTask[]>([])

  const titleRef = useRef<HTMLInputElement>(null)

  // Reset form when modal opens or task changes.
  /* eslint-disable react-hooks/set-state-in-effect -- intentional: synchronously populate form fields from task prop when modal opens; standard modal form-reset pattern */
  useEffect(() => {
    if (isOpen) {
      if (task) {
        setTitle(task.title)
        setProject(task.project)
        setPriority(task.priority)
        // task.status may hold a legacy value ('today'/'running') that is no longer a
        // selectable <option>; resolve it to a valid Kanban/inbox status so the <select>
        // always has a matching option to display.
        setStatus(task.status === 'inbox' ? 'inbox' : resolveBoardStatus(task))
        setBlocker(task.blocker)
        setCheckin(task.check_in_note)
        setSubtasks(task.subtasks ? task.subtasks.map((s) => ({ ...s })) : [])
      } else {
        setTitle('')
        setProject(defaultProject || '')
        setPriority('med')
        setStatus(
          defaultStatus === 'today' || defaultStatus === 'running'
            ? 'backlog'
            : defaultStatus || 'backlog'
        )
        setBlocker('')
        setCheckin('')
        setSubtasks([])
      }
      setTimeout(() => titleRef.current?.focus(), 100)
    }
  }, [isOpen, task, defaultStatus, defaultProject])
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleSave = useCallback(() => {
    const trimmedTitle = title.trim()
    if (!trimmedTitle) return
    onSave({
      title: trimmedTitle,
      project: project.trim(),
      priority,
      status,
      blocker: blocker.trim(),
      check_in_note: checkin.trim(),
      subtasks,
    })
  }, [title, project, priority, status, blocker, checkin, subtasks, onSave])

  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  function handleTitleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSave()
    }
  }

  const showBlocker = status === 'waiting'
  const showCheckin = status === 'in-progress' || status === 'waiting'
  const isEditMode = task !== null

  return (
    <div
      className={`modal-overlay fixed inset-0 bg-black/40 items-center justify-center z-[100] ${isOpen ? ' active flex' : ' hidden'}`}
      id="taskModal"
      onClick={handleOverlayClick}
    >
      <div className="modal bg-bg-elevated border border-border-default rounded-xl p-6 w-[420px] max-w-[90vw] shadow-modal">
        <h3 className="text-[1.05rem] font-bold text-text-primary mb-4" id="modalTitle">
          {isEditMode ? 'Edit Task' : 'New Task'}
        </h3>

        <div className="modal-field mb-3">
          <label className="block text-sm font-semibold text-text-secondary mb-1">Title</label>
          <input
            type="text"
            id="modalTaskTitle"
            className="w-full bg-bg-surface border border-border-default rounded-md py-2.5 px-3 text-[0.95rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            placeholder="Task title..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={handleTitleKeyDown}
            ref={titleRef}
          />
        </div>

        <div className="modal-field mb-3">
          <label className="block text-sm font-semibold text-text-secondary mb-1">Repo</label>
          <select
            id="modalTaskProject"
            className="w-full bg-bg-surface border border-border-default rounded-md py-2.5 px-3 text-[0.95rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            value={project}
            onChange={(e) => setProject(e.target.value)}
          >
            <option value="">No repo</option>
            {repos.map((repo) => (
              <option key={repo.id} value={repo.name}>
                {repo.name}
              </option>
            ))}
            {/* Preserve a legacy value that no longer matches any known repo, rather than silently discarding it. */}
            {project && !repos.some((repo) => repo.name === project) && (
              <option value={project}>{project}</option>
            )}
          </select>
        </div>

        <div className="modal-field mb-3">
          <label className="block text-sm font-semibold text-text-secondary mb-1">Priority</label>
          <select
            id="modalTaskPriority"
            className="w-full bg-bg-surface border border-border-default rounded-md py-2.5 px-3 text-[0.95rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            value={priority}
            onChange={(e) => setPriority(e.target.value as 'high' | 'med' | 'low')}
          >
            <option value="med">Med</option>
            <option value="high">High</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="modal-field mb-3">
          <label className="block text-sm font-semibold text-text-secondary mb-1">Status</label>
          <select
            id="modalTaskStatus"
            className="w-full bg-bg-surface border border-border-default rounded-md py-2.5 px-3 text-[0.95rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="inbox">Inbox</option>
            <option value="backlog">Backlog</option>
            <option value="in-progress">In Progress</option>
            <option value="waiting">Waiting On</option>
            <option value="review">Review</option>
            <option value="done">Done</option>
          </select>
        </div>

        <div className={`modal-field mb-2.5${showBlocker ? '' : ' hidden'}`} id="blockerField">
          <label className="block text-sm font-semibold text-text-secondary mb-1">
            Blocker / Waiting On
          </label>
          <input
            type="text"
            id="modalTaskBlocker"
            className="w-full bg-bg-surface border border-border-default rounded-md py-2.5 px-3 text-[0.95rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            placeholder="Person or blocker description"
            value={blocker}
            onChange={(e) => setBlocker(e.target.value)}
          />
        </div>

        <div className={`modal-field mb-2.5${showCheckin ? '' : ' hidden'}`} id="checkinField">
          <label className="block text-sm font-semibold text-text-secondary mb-1">
            Check-in Note
          </label>
          <input
            type="text"
            id="modalTaskCheckin"
            className="w-full bg-bg-surface border border-border-default rounded-md py-2.5 px-3 text-[0.95rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            placeholder="Check-in note"
            value={checkin}
            onChange={(e) => setCheckin(e.target.value)}
          />
        </div>

        {task?.session_name && (
          <div className="modal-field mb-3" id="worktreeField">
            <label className="block text-sm font-semibold text-text-secondary mb-1">Worktree</label>
            <div className="text-[0.95rem] text-text-secondary py-1">
              {worktreeBranch ? `Worktree: ${worktreeBranch}` : 'No worktree'}
            </div>
          </div>
        )}

        <SubtaskEditor subtasks={subtasks} onChange={setSubtasks} />

        <div className="modal-actions flex justify-end gap-2.5 mt-5">
          <button
            className={`modal-btn delete py-[7px] px-4 rounded-md text-[0.92rem] font-semibold cursor-pointer border border-border-default transition-all duration-150 ease-[ease] bg-transparent hover:bg-priority-high-bg mr-auto text-priority-high border-priority-high${isEditMode ? '' : ' hidden'}`}
            id="modalDelete"
            type="button"
            onClick={onDelete}
          >
            Delete
          </button>
          <button
            className="modal-btn cancel py-[7px] px-4 rounded-md text-[0.92rem] font-semibold cursor-pointer border border-border-default transition-all duration-150 ease-[ease] bg-transparent text-text-secondary hover:bg-bg-surface"
            id="modalCancel"
            type="button"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="modal-btn primary py-[7px] px-4 rounded-md text-[0.92rem] font-semibold cursor-pointer border border-accent transition-all duration-150 ease-[ease] bg-accent text-white hover:bg-accent-hover"
            id="modalSave"
            type="button"
            onClick={handleSave}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
