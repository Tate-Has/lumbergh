import {
  GripVertical,
  Play,
  SendHorizonal,
  ChevronDown,
  ChevronRight,
  StickyNote,
  GitBranch,
  Loader2,
  MoreVertical,
  Trash2,
} from 'lucide-react'
import type { PromptTemplate } from '../utils/promptResolver'
import PromptMentionInput from './PromptMentionInput'
import MentionText from './MentionText'

interface Todo {
  text: string
  done: boolean
  description?: string
}

interface Props {
  todo: Todo
  index: number
  sessionName: string
  allPrompts: PromptTemplate[]
  isEditing: boolean
  editingText: string
  isExpanded: boolean
  editingDescription: string
  isDragging: boolean
  isDragOver: boolean
  isHighlighted: boolean
  overflowIndex: number | null
  availableSessions: { name: string; displayName?: string }[]
  overflowRef: React.RefObject<HTMLDivElement | null>
  isLaunching: boolean
  launchError: string | null
  onToggle: (index: number) => void
  onStartEdit: (index: number) => void
  onSaveEdit: () => void
  onEditTextChange: (text: string) => void
  onEditKeyDown: (e: React.KeyboardEvent) => void
  onToggleExpand: (index: number) => void
  onDescriptionChange: (desc: string) => void
  onSaveDescription: (index: number) => void
  onDescriptionKeyDown: (e: React.KeyboardEvent) => void
  onSendToTerminal: (index: number, sendEnter: boolean) => void
  onLaunchWorktree: (index: number) => void
  onDelete: (index: number) => void
  onToggleOverflow: (index: number) => void
  onMoveTodo: (index: number, targetSession: string) => void
  onDragStart: (index: number) => void
  onDragOver: (e: React.DragEvent, index: number) => void
  onDragEnd: () => void
}

/** The row's second-string actions, kept out of the row itself so the two that get
 * clicked every day — launch a worker, send the text — stay reachable on a phone. */
function TodoOverflowMenu({
  index,
  availableSessions,
  overflowRef,
  onSendToTerminal,
  onDelete,
  onMoveTodo,
}: {
  index: number
  availableSessions: { name: string; displayName?: string }[]
  overflowRef: React.RefObject<HTMLDivElement | null>
  onSendToTerminal: (index: number, sendEnter: boolean) => void
  onDelete: (index: number) => void
  onMoveTodo: (index: number, targetSession: string) => void
}) {
  return (
    <div ref={overflowRef} className="px-3 py-2 border-t border-border-default space-y-2">
      <div className="flex flex-wrap gap-1">
        <button
          data-testid="todo-send-enter"
          onClick={() => onSendToTerminal(index, true)}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-control-bg hover:bg-action text-text-secondary hover:text-white rounded-[var(--radius-md)] transition-colors"
        >
          <SendHorizonal size={13} /> Send + Enter
        </button>
        <button
          onClick={() => onDelete(index)}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-control-bg hover:bg-danger text-text-secondary hover:text-white rounded-[var(--radius-md)] transition-colors"
        >
          <Trash2 size={13} /> Delete
        </button>
      </div>
      <div>
        <div className="text-xs text-text-muted mb-1">Move to:</div>
        {availableSessions.length === 0 ? (
          <div className="text-xs text-text-muted">No other sessions available</div>
        ) : (
          <div className="flex flex-wrap gap-1">
            {availableSessions.map((s) => (
              <button
                key={s.name}
                onClick={() => onMoveTodo(index, s.name)}
                className="px-2 py-1 text-xs bg-control-bg hover:bg-action text-text-secondary hover:text-white rounded-[var(--radius-md)] transition-colors"
              >
                {s.displayName || s.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TodoRowActions({
  index,
  isLaunching,
  onLaunchWorktree,
  onSendToTerminal,
}: {
  index: number
  isLaunching: boolean
  onLaunchWorktree: (index: number) => void
  onSendToTerminal: (index: number, sendEnter: boolean) => void
}) {
  return (
    <>
      <button
        data-testid="todo-launch-worktree"
        onClick={() => onLaunchWorktree(index)}
        disabled={isLaunching}
        className="text-text-muted hover:text-success disabled:hover:text-text-muted transition-colors px-1"
        title="Launch a worker on this in its own worktree"
      >
        {isLaunching ? <Loader2 size={18} className="animate-spin" /> : <GitBranch size={18} />}
      </button>
      <button
        data-testid="todo-send"
        onClick={() => onSendToTerminal(index, false)}
        className="text-text-muted hover:text-warning transition-colors px-1"
        title="Send text to this terminal (no Enter)"
      >
        <Play size={18} />
      </button>
    </>
  )
}

function TodoTrailingActions({
  index,
  done,
  hasSession,
  isOverflowOpen,
  onToggleOverflow,
  onDelete,
}: {
  index: number
  done: boolean
  hasSession: boolean
  isOverflowOpen: boolean
  onToggleOverflow: (index: number) => void
  onDelete: (index: number) => void
}) {
  if (done) {
    return (
      <button
        onClick={() => onDelete(index)}
        className="text-sm text-danger/50 hover:text-danger transition-colors px-1"
        title="Delete task"
      >
        <Trash2 size={16} />
      </button>
    )
  }
  if (!hasSession) return null
  return (
    <button
      data-testid="todo-overflow"
      onClick={() => onToggleOverflow(index)}
      className={`text-sm text-text-muted hover:text-text-primary transition-colors px-1 ${isOverflowOpen ? 'text-text-primary' : ''}`}
      title="More actions"
    >
      <MoreVertical size={16} />
    </button>
  )
}

function TodoText({
  todo,
  index,
  isExpanded,
  allPrompts,
  onStartEdit,
}: {
  todo: Todo
  index: number
  isExpanded: boolean
  allPrompts: PromptTemplate[]
  onStartEdit: (index: number) => void
}) {
  return (
    <span
      onClick={() => onStartEdit(index)}
      className={`flex-1 cursor-text ${
        todo.done ? 'text-text-muted line-through' : 'text-text-primary'
      }`}
    >
      {todo.done ? todo.text : <MentionText text={todo.text} prompts={allPrompts} />}
      {todo.description && !isExpanded && (
        <span className="ml-2 inline-flex" title="Has description">
          <StickyNote size={14} className="text-text-muted" />
        </span>
      )}
    </span>
  )
}

export default function TodoItem({
  todo,
  index,
  sessionName,
  allPrompts,
  isEditing,
  editingText,
  isExpanded,
  editingDescription,
  isDragging,
  isDragOver,
  isHighlighted,
  overflowIndex,
  availableSessions,
  overflowRef,
  isLaunching,
  launchError,
  onToggle,
  onStartEdit,
  onSaveEdit,
  onEditTextChange,
  onEditKeyDown,
  onToggleExpand,
  onDescriptionChange,
  onSaveDescription,
  onDescriptionKeyDown,
  onSendToTerminal,
  onLaunchWorktree,
  onDelete,
  onToggleOverflow,
  onMoveTodo,
  onDragStart,
  onDragOver,
  onDragEnd,
}: Props) {
  return (
    <div
      className={`bg-bg-surface rounded border border-border-default ${
        isDragging ? 'opacity-50' : ''
      } ${isDragOver ? 'border-action' : ''} ${isHighlighted ? 'todo-highlight' : ''}`}
    >
      <div
        draggable
        onDragStart={() => onDragStart(index)}
        onDragOver={(e) => onDragOver(e, index)}
        onDragEnd={onDragEnd}
        className="flex items-center gap-3 px-3 py-1 cursor-grab active:cursor-grabbing"
      >
        <GripVertical size={16} className="text-text-muted select-none" />
        {sessionName && !todo.done && (
          <TodoRowActions
            index={index}
            isLaunching={isLaunching}
            onLaunchWorktree={onLaunchWorktree}
            onSendToTerminal={onSendToTerminal}
          />
        )}
        <button
          onClick={() => onToggleExpand(index)}
          className="w-8 h-8 flex items-center justify-center text-text-muted hover:text-text-secondary hover:bg-control-bg rounded-[var(--radius-md)] transition-colors text-xl"
          title={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>
        {isEditing ? (
          <PromptMentionInput
            value={editingText}
            onChange={onEditTextChange}
            prompts={allPrompts}
            onBlur={onSaveEdit}
            onKeyDown={onEditKeyDown}
            autoFocus
            containerClassName="flex-1 min-w-0"
            className="w-full px-2 py-1 bg-input-bg text-text-primary text-base rounded-[var(--radius-lg)] border border-action focus:outline-none"
          />
        ) : (
          <TodoText
            todo={todo}
            index={index}
            isExpanded={isExpanded}
            allPrompts={allPrompts}
            onStartEdit={onStartEdit}
          />
        )}
        <TodoTrailingActions
          index={index}
          done={todo.done}
          hasSession={Boolean(sessionName)}
          isOverflowOpen={overflowIndex === index}
          onToggleOverflow={onToggleOverflow}
          onDelete={onDelete}
        />
        <input
          type="checkbox"
          checked={todo.done}
          onChange={() => onToggle(index)}
          data-testid="todo-checkbox"
          className="w-5 h-5 rounded bg-bg-surface border-input-border text-action focus:ring-action accent-action"
        />
      </div>
      {launchError && (
        <div className="px-3 pb-2 text-xs text-danger" data-testid="todo-launch-error">
          {launchError}
        </div>
      )}
      {overflowIndex === index && (
        <TodoOverflowMenu
          index={index}
          availableSessions={availableSessions}
          overflowRef={overflowRef}
          onSendToTerminal={onSendToTerminal}
          onDelete={onDelete}
          onMoveTodo={onMoveTodo}
        />
      )}
      {isExpanded && (
        <div className="px-3 pb-3 pt-0">
          <PromptMentionInput
            value={editingDescription}
            onChange={onDescriptionChange}
            prompts={allPrompts}
            onBlur={() => onSaveDescription(index)}
            onKeyDown={onDescriptionKeyDown}
            placeholder="Add details, context, acceptance criteria... (use @ to reference prompts)"
            multiline
            rows={5}
            autoFocus
            className="w-full h-32 px-3 py-2 bg-input-bg text-text-primary text-sm rounded-[var(--radius-lg)] border border-input-border focus:outline-none focus:border-action/50 resize-y"
          />
        </div>
      )}
    </div>
  )
}
