import React, { useRef } from 'react'
import type { SubTask } from '../../types/focus'

export interface SubtaskEditorProps {
  subtasks: SubTask[]
  onChange: (subtasks: SubTask[]) => void
}

export default function SubtaskEditor({ subtasks, onChange }: SubtaskEditorProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  function addSubtask() {
    const input = inputRef.current
    if (!input) return
    const text = input.value.trim()
    if (!text) return
    onChange([...subtasks, { text, done: false }])
    input.value = ''
    input.focus()
  }

  function toggleDone(index: number) {
    const updated = subtasks.map((st, i) => (i === index ? { ...st, done: !st.done } : st))
    onChange(updated)
  }

  function updateText(index: number, text: string) {
    const updated = subtasks.map((st, i) => (i === index ? { ...st, text } : st))
    onChange(updated)
  }

  function removeSubtask(index: number) {
    onChange(subtasks.filter((_, i) => i !== index))
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      addSubtask()
    }
  }

  return (
    <div className="modal-field" id="subtasksField">
      <label className="block text-xs font-semibold text-text-secondary mb-1">Subtasks</label>
      <div
        id="modalSubtaskList"
        className="subtask-list flex flex-col gap-1.5 max-h-[200px] overflow-y-auto mb-2"
      >
        {subtasks.map((st, i) => (
          <div className="subtask-row flex items-center gap-2" key={i}>
            <input
              type="checkbox"
              className="subtask-check shrink-0 w-4 h-4 accent-accent"
              checked={st.done}
              onChange={() => toggleDone(i)}
            />
            <input
              type="text"
              className="subtask-text flex-1 py-1 px-1.5 text-[0.85rem] border border-border-default rounded bg-bg-base text-text-primary"
              value={st.text}
              onChange={(e) => updateText(i, e.target.value)}
            />
            <button
              className="subtask-delete bg-transparent border-none text-text-secondary cursor-pointer text-base px-1 leading-none hover:text-priority-high"
              title="Remove"
              type="button"
              onClick={() => removeSubtask(i)}
            >
              &times;
            </button>
          </div>
        ))}
      </div>
      <div className="subtask-add-row flex gap-2 items-center">
        <input
          type="text"
          id="modalNewSubtask"
          className="flex-1 py-1 px-1.5 text-[0.85rem] border border-border-default rounded bg-bg-base text-text-primary"
          placeholder="Add subtask..."
          ref={inputRef}
          onKeyDown={handleKeyDown}
        />
        <button
          className="modal-btn py-1 px-2.5 text-[0.85rem]"
          id="modalAddSubtask"
          type="button"
          onClick={addSubtask}
        >
          +
        </button>
      </div>
    </div>
  )
}
