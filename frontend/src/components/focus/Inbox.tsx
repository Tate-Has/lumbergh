import React, { useState, useRef, useEffect, useCallback } from 'react'
import type { Task } from '../../types/focus'

interface InboxProps {
  tasks: Task[]
  isOpen: boolean
  onToggleOpen: () => void
  onAddTask: (title: string) => void
  onEditTask: (task: Task) => void
  onUpdateTitle: (taskId: string, newTitle: string) => void
  getDragHandlers: (taskId: string) => {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragEnd: (e: React.DragEvent) => void
  }
  dropZoneHandlers: {
    onDragOver: (e: React.DragEvent) => void
    onDragLeave: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
  }
  inputRef?: React.RefObject<HTMLInputElement | null>
}

export default function Inbox({
  tasks,
  isOpen,
  onToggleOpen,
  onAddTask,
  onEditTask,
  onUpdateTitle,
  getDragHandlers,
  dropZoneHandlers,
  inputRef: externalInputRef,
}: InboxProps) {
  const [inputValue, setInputValue] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const internalInputRef = useRef<HTMLInputElement>(null)
  const inputRef = externalInputRef ?? internalInputRef
  const editInputRef = useRef<HTMLInputElement>(null)

  const inboxTasks = tasks.filter((t) => t.status === 'inbox')

  // Focus inline edit input when editingId changes
  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingId])

  /* eslint-disable react-hooks/preserve-manual-memoization -- inputRef is a stable ref object; omitting it from deps is intentional */
  const handleQuickCapture = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && inputValue.trim()) {
        onAddTask(inputValue.trim())
        setInputValue('')
        inputRef.current?.focus()
      }
    },
    [inputValue, onAddTask]
  )

  const handleAddBtnClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      if (!isOpen) {
        onToggleOpen()
      }
      // Small delay to let the section expand before focusing
      setTimeout(() => inputRef.current?.focus(), 50)
    },
    [isOpen, onToggleOpen]
  )
  /* eslint-enable react-hooks/preserve-manual-memoization */

  const startEditing = useCallback((task: Task) => {
    setEditingId(task.id)
    setEditValue(task.title)
  }, [])

  const commitEdit = useCallback(() => {
    if (editingId && editValue.trim()) {
      onUpdateTitle(editingId, editValue.trim())
    }
    setEditingId(null)
    setEditValue('')
  }, [editingId, editValue, onUpdateTitle])

  const cancelEdit = useCallback(() => {
    setEditingId(null)
    setEditValue('')
  }, [])

  const handleEditKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        ;(e.target as HTMLInputElement).blur()
      } else if (e.key === 'Escape') {
        cancelEdit()
      }
    },
    [cancelEdit]
  )

  return (
    <div
      className={`inbox-strip bg-bg-elevated border border-border-subtle rounded-xl overflow-hidden transition-[max-height] duration-[250ms] ease-[ease] shrink-0${isOpen ? ' expanded max-h-[500px]' : ' collapsed max-h-[46px]'}`}
      id="inboxStrip"
    >
      <div
        className="inbox-header flex items-center justify-between py-3 px-4 cursor-pointer select-none hover:bg-bg-surface"
        onClick={onToggleOpen}
      >
        <div className="inbox-header-left flex items-center gap-2">
          <span className="section-title text-[0.85rem] font-semibold text-text-secondary uppercase tracking-[0.04em]">
            Inbox
          </span>
          <span
            className="section-count text-xs font-semibold text-text-muted bg-bg-surface rounded-[10px] px-2.5 py-0.5 ml-2.5"
            id="inboxCount"
          >
            {inboxTasks.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="inbox-add-btn bg-transparent border border-border-default rounded-md w-[26px] h-[26px] flex items-center justify-center text-base font-medium text-text-muted cursor-pointer transition-all duration-150 ease-[ease] hover:border-accent hover:text-accent hover:bg-orange-subtle"
            id="inboxAddBtn"
            title="Quick capture"
            onClick={handleAddBtnClick}
          >
            +
          </button>
          <span
            className={`inbox-chevron text-xs text-text-muted transition-transform duration-200 ease-[ease] cursor-pointer${isOpen ? ' rotate-180' : ''}`}
            id="inboxChevron"
          >
            &#9660;
          </span>
        </div>
      </div>
      <div className="inbox-body px-4 pb-4 pt-2">
        <div className="inbox-input-row flex gap-2 mb-3">
          <input
            ref={inputRef}
            type="text"
            className="inbox-input flex-1 bg-bg-surface border border-border-subtle rounded-md py-2.5 px-3.5 text-[0.82rem] text-text-primary outline-none transition-[border-color] duration-150 focus:border-accent placeholder:text-text-muted"
            id="inboxInput"
            placeholder="Capture a task..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleQuickCapture}
          />
        </div>
        <div
          className="inbox-items flex flex-col gap-1 max-h-[300px] overflow-y-auto"
          id="inboxItems"
          {...dropZoneHandlers}
        >
          {inboxTasks.map((task) => {
            const dragHandlers = getDragHandlers(task.id)
            return (
              <div
                key={task.id}
                className="inbox-item flex items-center justify-between py-2 px-3 rounded-md bg-bg-surface transition-all duration-150 ease-[ease]"
                data-task-id={task.id}
                draggable={dragHandlers.draggable}
                onDragStart={dragHandlers.onDragStart}
                onDragEnd={dragHandlers.onDragEnd}
              >
                <span className="inbox-drag-grip" title="Drag to board or today">
                  &#x2630;
                </span>
                {editingId === task.id ? (
                  <input
                    ref={editInputRef}
                    className="inbox-item-title-input flex-1 bg-bg-surface border border-border-subtle rounded py-1 px-1.5 text-[0.82rem] text-text-primary outline-none"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onBlur={commitEdit}
                    onKeyDown={handleEditKeyDown}
                  />
                ) : (
                  <span
                    className="inbox-item-title text-[0.82rem] font-medium text-text-primary cursor-text flex-1"
                    data-task-id={task.id}
                    onClick={() => startEditing(task)}
                  >
                    {task.title}
                  </span>
                )}
                <button
                  className="promote-btn bg-transparent border border-border-default rounded-[5px] py-0.5 px-2 text-[0.7rem] font-semibold text-accent cursor-pointer transition-all duration-150 ease-[ease] whitespace-nowrap hover:bg-orange-subtle hover:border-accent"
                  data-task-id={task.id}
                  title="Add details"
                  onClick={(e) => {
                    e.stopPropagation()
                    onEditTask(task)
                  }}
                >
                  &rarr;
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
