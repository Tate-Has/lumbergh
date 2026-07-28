import { useState } from 'react'
import type { Task } from '../../types/focus'
import type { SessionStatusInfo } from '../../hooks/useSessionStatus'
import { statusColorClasses } from '../../utils/sessionStatus'

export interface AttentionStripProps {
  /** Tasks needing attention, from useAttentionItems. Strip renders nothing if empty. */
  attentionItems: Task[]
  /** Live status per session_name, from useSessionStatus — drives the dot color/label. */
  sessionStatusMap: Record<string, SessionStatusInfo>
  /**
   * Optional branch lookup for the "repo · branch" subline, keyed by task.id or
   * task.session_name (whichever the caller has handy — both keys are tried).
   */
  worktreeBranches?: Record<string, string>
  onEditTask: (task: Task) => void
}

interface AttentionCardProps {
  task: Task
  status: SessionStatusInfo | undefined
  branch: string | undefined
  onEditTask: (task: Task) => void
}

function AttentionStatusRow({ status }: { status: SessionStatusInfo | undefined }) {
  const color = status?.color || 'gray'
  const dotClass = statusColorClasses[color]?.dot || 'bg-gray-500'
  const textClass = statusColorClasses[color]?.text || 'text-text-tertiary'
  const pulseClass = status?.pulse ? 'animate-pulse' : ''

  return (
    <div className="attention-card-status flex items-center gap-[5px] mb-1.5">
      <span className={`session-dot w-2 h-2 rounded-full shrink-0 ${dotClass} ${pulseClass}`} />
      <span className={`text-[0.76rem] font-semibold uppercase tracking-[0.03em] ${textClass}`}>
        {status?.label || 'Unknown'}
      </span>
    </div>
  )
}

function AttentionMeta({ project, branch }: { project: string; branch: string | undefined }) {
  const separator = project && branch ? ' · ' : ''

  return (
    <div className="attention-card-meta text-[0.82rem] font-medium text-text-muted mb-1 truncate">
      {project}
      {separator}
      {branch && <span className="font-mono">{branch}</span>}
    </div>
  )
}

function AttentionCard({ task, status, branch, onEditTask }: AttentionCardProps) {
  const showMeta = !!task.project || !!branch

  return (
    <button
      className="attention-card shrink-0 w-[220px] text-left bg-bg-surface border border-border-default rounded-lg px-3 py-2.5 shadow-card cursor-pointer transition-all duration-150 hover:border-accent hover:shadow-card-hover"
      onClick={() => onEditTask(task)}
    >
      <AttentionStatusRow status={status} />
      <div className="attention-card-title text-[0.92rem] font-semibold text-text-primary mb-1 truncate">
        {task.title}
      </div>
      {showMeta && <AttentionMeta project={task.project} branch={branch} />}
      {status?.label && (
        <div className="attention-card-reason text-[0.85rem] text-text-secondary truncate">
          {status.label}
        </div>
      )}
    </button>
  )
}

export default function AttentionStrip({
  attentionItems,
  sessionStatusMap,
  worktreeBranches,
  onEditTask,
}: AttentionStripProps) {
  const [isOpen, setIsOpen] = useState(true)

  if (attentionItems.length === 0) return null

  return (
    <div
      className={`attention-strip bg-status-waiting-bg border border-status-waiting rounded-xl overflow-hidden transition-[max-height] duration-[250ms] ease-[ease] shrink-0${isOpen ? ' max-h-[220px]' : ' collapsed max-h-[46px]'}`}
      id="attentionStrip"
    >
      <div
        className="attention-header flex items-center justify-between py-3 px-4 cursor-pointer select-none hover:bg-status-waiting-bg/70"
        id="attentionHeader"
        onClick={() => setIsOpen((v) => !v)}
      >
        <div className="attention-header-left flex items-center gap-2">
          <span className="section-title text-[0.98rem] font-semibold text-status-waiting uppercase tracking-[0.04em] m-0">
            Needs Your Attention
          </span>
          <span className="section-count text-sm font-semibold text-status-waiting bg-bg-surface rounded-[10px] px-2.5 py-0.5">
            {attentionItems.length}
          </span>
        </div>
        <span
          className={`attention-chevron text-sm text-status-waiting transition-transform duration-200 ease-[ease] ${isOpen ? ' rotate-180' : ''}`}
        >
          &#9660;
        </span>
      </div>
      <div className="attention-body flex gap-3 overflow-x-auto px-4 pb-4" id="attentionBody">
        {attentionItems.map((task) => {
          const status = task.session_name ? sessionStatusMap[task.session_name] : undefined
          const branch =
            worktreeBranches?.[task.id] ||
            (task.session_name ? worktreeBranches?.[task.session_name] : undefined)

          return (
            <AttentionCard
              key={task.id}
              task={task}
              status={status}
              branch={branch}
              onEditTask={onEditTask}
            />
          )
        })}
      </div>
    </div>
  )
}
