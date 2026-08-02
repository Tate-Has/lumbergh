import { useNavigate } from 'react-router-dom'
import {
  Minus,
  Pause,
  Play,
  AlertCircle,
  Circle,
  Hand,
  MessageCircleQuestion,
  X,
} from 'lucide-react'
import type { SessionBase } from '../utils/sessionStatus'
import { getSessionStatus, statusColorClasses } from '../utils/sessionStatus'

interface Worker extends SessionBase {
  type?: 'direct' | 'worktree' | 'scratch'
  workdir?: string | null
  worktreeBranch?: string | null
}

const statusIcons = {
  gray: Minus,
  yellow: Pause,
  green: Circle,
  red: AlertCircle,
} as const

function workerIcon(worker: Worker) {
  const base = getSessionStatus(worker)
  let Icon = statusIcons[base.color as keyof typeof statusIcons] || Circle
  if (worker.idleState === 'working') Icon = Play
  if (worker.idleState === 'blocked') Icon = Hand
  if (worker.needsAnswer && worker.idleState === 'idle') Icon = MessageCircleQuestion
  return { ...base, Icon }
}

/** A compact, low-detail worker row shown nested under its overseer. Deliberately
 * strips the full card down to status, name, state, and a delete — no cloud/star/
 * windows/description/agent/pause/edit. */
export default function WorkerRow({
  worker,
  onDelete,
}: {
  worker: Worker
  onDelete: (name: string, cleanupWorktree?: boolean) => void
}) {
  const navigate = useNavigate()
  const status = workerIcon(worker)
  const colors = statusColorClasses[status.color]
  const label = worker.displayName || worker.name

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm(`Delete worker "${worker.name}" and its worktree?`)) {
      onDelete(worker.name, worker.type === 'worktree')
    }
  }

  return (
    <div
      onClick={() => navigate(`/session/${worker.name}`)}
      data-testid={`worker-row-${worker.name}`}
      className="group flex items-center gap-2 py-1.5 pl-3 pr-2 rounded-[var(--radius-md)] hover:bg-bg-glass-hover cursor-pointer transition-colors"
    >
      <span
        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${colors.dot} ${status.pulse ? 'animate-pulse' : ''}`}
        title={status.label}
      />
      <span className="text-sm text-text-secondary truncate min-w-0">{label}</span>
      <span className={`flex items-center gap-1 ${colors.text} text-xs flex-shrink-0`}>
        <status.Icon size={12} />
        <span className="hidden sm:inline">{status.label}</span>
      </span>
      <button
        onClick={handleDelete}
        title="Delete worker"
        className="ml-auto flex-shrink-0 p-1 rounded text-text-muted opacity-0 group-hover:opacity-100 hover:text-danger transition-all"
      >
        <X size={14} />
      </button>
    </div>
  )
}
