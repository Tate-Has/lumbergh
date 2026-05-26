import React, { useState, useEffect, useRef, useCallback } from 'react'
import SubtaskEditor from './SubtaskEditor'
import type { Task, SubTask } from '../../types/focus'

export interface TaskModalProps {
  isOpen: boolean
  task: Task | null
  defaultStatus: string
  projects: string[]
  onSave: (data: Partial<Task> & { title: string }) => void
  onDelete: () => void
  onClose: () => void
}

export default function TaskModal({
  isOpen,
  task,
  defaultStatus,
  projects,
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
        setStatus(task.status)
        setBlocker(task.blocker)
        setCheckin(task.check_in_note)
        setSubtasks(task.subtasks ? task.subtasks.map((s) => ({ ...s })) : [])
      } else {
        setTitle('')
        setProject('')
        setPriority('med')
        setStatus(defaultStatus || 'today')
        setBlocker('')
        setCheckin('')
        setSubtasks([])
      }
      setTimeout(() => titleRef.current?.focus(), 100)
    }
  }, [isOpen, task, defaultStatus])
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
  const showCheckin = status === 'running' || status === 'waiting'
  const isEditMode = task !== null

  return (
    <div
      className={`modal-overlay fixed inset-0 bg-black/40 items-center justify-center z-[100] ${isOpen ? ' active flex' : ' hidden'}`}
      id="taskModal"
      onClick={handleOverlayClick}
    >
      <div className="modal bg-bg-elevated border border-border-default rounded-xl p-6 w-[420px] max-w-[90vw] shadow-modal">
        <h3 className="text-[0.95rem] font-bold text-text-primary mb-4" id="modalTitle">
          {isEditMode ? 'Edit Task' : 'New Task'}
        </h3>

        <div className="modal-field mb-3">
          <label className="block text-xs font-semibold text-text-secondary mb-1">Title</label>
          <input
            type="text"
            id="modalTaskTitle"
            className="w-full bg-bg-surface border border-border-subtle rounded-md py-2.5 px-3 text-[0.82rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            placeholder="Task title..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={handleTitleKeyDown}
            ref={titleRef}
          />
        </div>

        <div className="modal-field mb-3">
          <label className="block text-xs font-semibold text-text-secondary mb-1">Project</label>
          <input
            type="text"
            id="modalTaskProject"
            className="w-full bg-bg-surface border border-border-subtle rounded-md py-2.5 px-3 text-[0.82rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            placeholder="Optional project tag"
            list="projectSuggestions"
            autoComplete="off"
            value={project}
            onChange={(e) => setProject(e.target.value)}
          />
          <datalist id="projectSuggestions">
            {projects.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </div>

        <div className="modal-field mb-3">
          <label className="block text-xs font-semibold text-text-secondary mb-1">Priority</label>
          <select
            id="modalTaskPriority"
            className="w-full bg-bg-surface border border-border-subtle rounded-md py-2.5 px-3 text-[0.82rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            value={priority}
            onChange={(e) => setPriority(e.target.value as 'high' | 'med' | 'low')}
          >
            <option value="med">Med</option>
            <option value="high">High</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="modal-field mb-3">
          <label className="block text-xs font-semibold text-text-secondary mb-1">Status</label>
          <select
            id="modalTaskStatus"
            className="w-full bg-bg-surface border border-border-subtle rounded-md py-2.5 px-3 text-[0.82rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="today">Today</option>
            <option value="inbox">Inbox</option>
            <option value="backlog">Backlog</option>
            <option value="in-progress">In Progress</option>
            <option value="waiting">Waiting On</option>
            <option value="review">Review</option>
            <option value="running">Running</option>
            <option value="done">Done</option>
          </select>
        </div>

        <div className={`modal-field mb-2.5${showBlocker ? '' : ' hidden'}`} id="blockerField">
          <label className="block text-xs font-semibold text-text-secondary mb-1">
            Blocker / Waiting On
          </label>
          <input
            type="text"
            id="modalTaskBlocker"
            className="w-full bg-bg-surface border border-border-subtle rounded-md py-2.5 px-3 text-[0.82rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            placeholder="Person or blocker description"
            value={blocker}
            onChange={(e) => setBlocker(e.target.value)}
          />
        </div>

        <div className={`modal-field mb-2.5${showCheckin ? '' : ' hidden'}`} id="checkinField">
          <label className="block text-xs font-semibold text-text-secondary mb-1">
            Check-in Note
          </label>
          <input
            type="text"
            id="modalTaskCheckin"
            className="w-full bg-bg-surface border border-border-subtle rounded-md py-2.5 px-3 text-[0.82rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent"
            placeholder="Check-in note"
            value={checkin}
            onChange={(e) => setCheckin(e.target.value)}
          />
        </div>

        <SubtaskEditor subtasks={subtasks} onChange={setSubtasks} />

        <div className="modal-actions flex justify-end gap-2.5 mt-5">
          <button
            className={`modal-btn delete py-[7px] px-4 rounded-md text-[0.8rem] font-semibold cursor-pointer border border-border-default transition-all duration-150 ease-[ease] bg-transparent hover:bg-priority-high-bg mr-auto text-priority-high border-priority-high${isEditMode ? '' : ' hidden'}`}
            id="modalDelete"
            type="button"
            onClick={onDelete}
          >
            Delete
          </button>
          <button
            className="modal-btn cancel py-[7px] px-4 rounded-md text-[0.8rem] font-semibold cursor-pointer border border-border-default transition-all duration-150 ease-[ease] bg-transparent text-text-secondary hover:bg-bg-surface"
            id="modalCancel"
            type="button"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="modal-btn primary py-[7px] px-4 rounded-md text-[0.8rem] font-semibold cursor-pointer border border-accent transition-all duration-150 ease-[ease] bg-accent text-white hover:bg-accent-hover"
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
