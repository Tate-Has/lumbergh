import { useMemo } from 'react'
import type { Task } from '../types/focus'
import type { SessionStatusInfo } from './useSessionStatus'
import { ATTENTION_IDLE_THRESHOLD_MS } from '../types/focusConstants'

function needsAttention(status: SessionStatusInfo): boolean {
  // Red covers both 'error' and 'stalled' underlying idle states — always attention-worthy.
  if (status.color === 'red') return true

  // Yellow covers 'idle' (labeled "Waiting for input") — only attention-worthy once it's
  // been sitting idle for at least ATTENTION_IDLE_THRESHOLD_MS.
  if (status.color === 'yellow' && status.idleStateUpdatedAt) {
    const idleSince = Date.parse(status.idleStateUpdatedAt)
    if (!Number.isNaN(idleSince) && Date.now() - idleSince >= ATTENTION_IDLE_THRESHOLD_MS) {
      return true
    }
  }

  return false
}

export function useAttentionItems(
  tasks: Task[],
  sessionStatusMap: Record<string, SessionStatusInfo>
): Task[] {
  return useMemo(() => {
    return tasks.filter((task) => {
      if (!task.session_name) return false
      const status = sessionStatusMap[task.session_name]
      if (!status) return false
      return needsAttention(status)
    })
  }, [tasks, sessionStatusMap])
}
